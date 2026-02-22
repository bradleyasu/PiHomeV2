import json
import os
import queue
import subprocess
import sys
from time import sleep

import ffmpeg
# Don't import sounddevice at module level - it initializes PortAudio and locks the DAC
# import sounddevice as sd
import numpy as np
from util.phlog import PIHOME_LOGGER
from util.configuration import CONFIG
from threading import Thread
import eyed3


SAVED_URL_JSON = "radio_stations.pihome"

# enum of audio states
class AudioState:
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2
    FETCHING = 3
    BUFFERING = 4

class AudioPlayer:
    percent = 0
    title = "No Media"
    volume = 1.0
    paused = False
    album_art = None
    queue = []
    queue_pos = 0
    data = None
    volume_listeners = []
    state_listeners = []
    saves_listeners = []
    percent = 100
    is_playing = False
    current_state = AudioState.STOPPED
    current_source = None
    player_thread = None
    current_folder = None
    """
    Saved urls is an array of json objects with a "text" and "url" key
    The text is the title of the media and the url is the url to the media
    an optional "thumbnail" icon can be added as album art
    """
    saved_urls =[]


    def __init__(self, device=None, blocksize=4096, buffersize=512):
        self.device = device
        self.blocksize = blocksize
        self.buffersize = buffersize
        # self.q = queue.Queue(maxsize=self.buffersize)
        self.q_in = queue.Queue()
        self.q_out = queue.Queue()
        self.q_raw = queue.Queue()
        self.stream = None
        self.process = None
        self.paused = False
        self.empty_buffer = False
        # Don't probe audio device at init - do it lazily when needed
        # This prevents locking the device when PiHome starts
        # if self.device is None:
        #     self.device = self.find_sound_device()

        # start audio procesing thread
        self.thread = Thread(target=self.audio_processing_thread, daemon=True)
        self.thread.start()

        # deserialize saved urls
        self.deserialize_saved_urls()

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()
    
    def __del__(self):
        self.cleanup()


    def serialize_saved_urls(self):
        """
        Serializes the saved urls to the SAVED_URL_JSON file on disk
        """
        with open(SAVED_URL_JSON, 'w') as f:
            f.write(json.dumps(self.saved_urls))

        self.notify_saves_listeners(self.saved_urls)
        PIHOME_LOGGER.info("Saved urls serialized to {}".format(SAVED_URL_JSON))

    def deserialize_saved_urls(self):
        """
        Deserializes the saved urls from the SAVED_URL_JSON file on disk
        """
        try:
            with open(SAVED_URL_JSON, 'r') as f:
                self.saved_urls = json.loads(f.read())
        except FileNotFoundError:
            self.saved_urls = []
            PIHOME_LOGGER.warn("No saved urls for radio stations found")
        
        # LOG Saved URLS
        for url in self.saved_urls:
            PIHOME_LOGGER.info("Loaded saved url into radio stations: {}".format(url))

    def save_current(self):
        if self.current_state == AudioState.PLAYING:
            self.add_save_current_from_json({})
        else:
            PIHOME_LOGGER.warn("Cannot save current url, no media playing")

    def remove_saved_url(self, url):
        for i, saved_url in enumerate(self.saved_urls):
            if saved_url["url"] == url:
                self.saved_urls.pop(i)
                self.serialize_saved_urls()
                return
    
    def add_save_current_from_json(self, json):
        """
        Similar to add_saved_url_from_json, but instead creates a directlink to the
        currently decoded url
        (wow. i hate this.  clean this up later)
        """
        if self.current_state != AudioState.PLAYING:
            PIHOME_LOGGER.warn("Cannot save current url, no media playing")
            return
        if "url" not in json:
            if self.current_folder is not None:
                json["url"] = self.current_folder
            else:
                json["url"] = self.current_source
        if "thumbnail" not in json:
            if self.current_folder is not None:
                json["thumbnail"] = None
            else:
                json["thumbnail"] = self.album_art
        if "text" not in json:
            if self.current_folder is not None:
                json["text"] = self.current_folder.split("/")[-1]
            else:
                json["text"] = self.title

        if not self.save_exists(json["url"]):
            self.saved_urls.append(json)
            self.serialize_saved_urls()
        else: 
            self.remove_saved_url(json["url"])

    def find_saved_url(self, url):
        for saved_url in self.saved_urls:
            if saved_url["url"] == url:
                return saved_url
        return None
    
    def save_exists(self, url):
        for saved_url in self.saved_urls:
            # if saved_url["url"] contains url anywhere in the string
            if url in saved_url["url"]:
                return True
        return False

    def add_saved_url_from_json(self, json):
        """
        Adds a saved url from a json object
        """
        self.saved_urls.append(json)
        self.serialize_saved_urls()

    def add_saved_url(self, text, url, thumbnail=None):
        """
        Adds a saved url to the saved urls list
        """
        self.saved_urls.append({"text": text, "url": url, "thumbnail": thumbnail})
        self.serialize_saved_urls()


    def find_sound_device(self):
        """Only called when device is not specified in config"""
        PIHOME_LOGGER.info("Auto-detecting sound device")
        # Lazy import sounddevice only when needed
        import sounddevice as sd
        try:
            devices = sd.query_devices()
            for device in devices:
                if device['max_output_channels'] > 0:
                    PIHOME_LOGGER.info(f"Found sound device: {device['name']}")
                    return device['name']
            PIHOME_LOGGER.error("NO SOUND DEVICE FOUND!")
            self.log_sound_devices()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error finding sound device: {e}")
        return None
    
    def log_sound_devices(self):
        import sounddevice as sd
        devices = sd.query_devices()
        PIHOME_LOGGER.warn("Sound Devices:")
        PIHOME_LOGGER.warn("-----------------")
        for device in devices:
            PIHOME_LOGGER.warn(device)
        PIHOME_LOGGER.warn("-----------------")
    
    def int_or_str(self, text):
        """Helper function for argument parsing."""
        try:
            return int(text)
        except ValueError:
            return text

    def add_volume_listener(self, listener):
        self.volume_listeners.append(listener)

    def add_state_listener(self, listener):
        self.state_listeners.append(listener)

    def notify_state_listeners(self, state):
        for listener in self.state_listeners:
            listener(state)

    def add_saves_listener(self, listener):
        self.saves_listeners.append(listener)
    
    def notify_saves_listeners(self, saves):
        for listener in self.saves_listeners:
            listener(saves)

    def set_state(self, state):
        self.current_state = state
        self.notify_state_listeners(state)

    def audio_processing_thread(self):
        PIHOME_LOGGER.info("Starting audio processing thread")
        while True:
            try:
                # data = self.q_in.get_nowait()
                data = self.q_in.get()
                # self.data = data
            except queue.Empty:
                continue

            # Perform the expensive operations here
            data = np.frombuffer(data, dtype='float32')
            self.q_out.put(data)
            # vol_data = data * self.volume
            # self.q_out.put(vol_data)
            # sleep(0.01)
        PIHOME_LOGGER.info("Exiting audio processing thread")

    def callback(self, outdata, frames, time, status):
        if status.output_underflow:
            print('Output underflow: increase blocksize?', file=sys.stderr)
            outdata[:] = bytes(len(outdata))
            return

        try:
            data = self.q_out.get_nowait()
            # data is a np.frombuffer but we need to set self.data to buffer
            self.data = data.tobytes()
        except queue.Empty:
            print('Buffer is empty: increase buffersize?', file=sys.stderr)
            outdata[:] = bytes(len(outdata))
            return

        # Convert the numpy array data to bytes
        vol_data = data * self.volume
        try:
            outdata[:] = vol_data.tobytes()
        except:
            self.stop()

    def play(self, url, reset_playlist=True):
        # ensure device is found - only auto-detect if not specified in config
        if self.device is None:
            self.device = self.find_sound_device()
            PIHOME_LOGGER.info(f"Auto-detected audio device: {self.device}")
        else:
            PIHOME_LOGGER.info(f"Using configured audio device: {self.device}")
        self.stop()
        if reset_playlist:
            self.clear_playlist()
        self.empty_buffer = False
        self.player_thread = Thread(target=self._play, args=(url,), daemon=True)
        self.player_thread.start()

    def _play(self, url):
        is_local = True
        self.current_source = url
        if url.startswith('http://') or url.startswith('https://'):
            self.set_state(AudioState.FETCHING)
            is_local = False
            url = self.run_youtubedl(url)

        if url.startswith("directlink:"):
            self.set_state(AudioState.BUFFERING)
            url = url.replace("directlink:", "")
            is_local = False
            saved = self.find_saved_url(url) 
            if saved is not None:
                self.title = saved["text"]
                self.album_art = saved["thumbnail"]
            

        if url.startswith("folder:"):
            self.clear_playlist()
            directory = url.replace("folder:", "")
            # iterate over all files in the directory and add them to the queue
            for file in os.listdir(directory):
                self.add_to_playlist(os.path.join(directory, file))
            self.play(self.queue[self.queue_pos], reset_playlist=False)
            self.album_art = None
            self.title = url.split("/")[-1]
            self.current_folder = url
            return

        if not is_local:
            try:
                info = ffmpeg.probe(url)
            except ffmpeg.Error as e:
                PIHOME_LOGGER.error(e)
                PIHOME_LOGGER.error(e.stderr)
                self.stop()
                return

            streams = info.get('streams', [])
            if len(streams) != 1:
                PIHOME_LOGGER.error('There must be exactly one stream available')
                self.stop()
                return
                

            stream = streams[0]

            if stream.get('codec_type') != 'audio':
                PIHOME_LOGGER.error('The stream must be an audio stream')
                return

            channels = stream['channels']
            samplerate = float(stream['sample_rate'])
        else:
            channels = 2
            samplerate = 44100
            self.extract_metadata(url)
            
        self.set_state(AudioState.BUFFERING)
        try:
            PIHOME_LOGGER.info('Opening stream {} ...'.format(url))
            self.process = ffmpeg.input(url).output(
                'pipe:',
                format='f32le',
                acodec='pcm_f32le',
                ac=channels,
                ar=samplerate,
                loglevel='quiet',
                reconnect=1,
                reconnect_streamed=1,
                reconnect_delay_max=5,
            ).run_async(pipe_stdout=True)
            # Lazy import sounddevice when actually playing
            import sounddevice as sd
            self.stream = sd.RawOutputStream(samplerate=samplerate, blocksize=self.blocksize, device=self.device, channels=channels, dtype='float32', callback=self.callback)
            read_size = self.blocksize * channels * self.stream.samplesize
            PIHOME_LOGGER.info('Buffering {} ...'.format(url))
            for _ in range(self.buffersize):
                self.q_in.put_nowait(self.process.stdout.read(read_size))
            PIHOME_LOGGER.info('Starting Playback {} ...'.format(url))
            self.set_state(AudioState.PLAYING)
            with self.stream:
                timeout = self.blocksize * self.buffersize / samplerate
                code =self.process.poll()
                while code is None and not self.empty_buffer:
                    while True:
                        d = self.process.stdout.read(read_size)
                        if not d:
                            break
                        self.q_in.put(d, timeout=timeout)
                PIHOME_LOGGER.info('End of stream. {}'.format(url))
                self.next()
        except KeyboardInterrupt:
            self.stop()
            PIHOME_LOGGER.info('Interrupted by user')
            return
        except queue.Full:
            # A timeout occurred, i.e. there was an error in the callback
            self.stop()
            PIHOME_LOGGER.error('Error: Buffer is full')
            # time.sleep(0.5)
            return
        except (ConnectionResetError, ConnectionAbortedError, TimeoutError) as e:
            self.stop()
            PIHOME_LOGGER.error("Connection Error")
        except Exception as e:
            self.stop()
            PIHOME_LOGGER.error("Other Error")
            PIHOME_LOGGER.error(e)
            return

    def extract_metadata(self, url):
        if not url.endswith(".mp3"):
            return

        try:
            audiofile = eyed3.load(url)
            self.title = audiofile.tag.title
            album_art = audiofile.tag.images[0].image_data
            if album_art:
                with open("current_album_art.jpg", "wb") as f:
                    f.write(album_art)
                self.album_art = "current_album_art.jpg"
            else:
                self.album_art = None
        
        except Exception as e:
            PIHOME_LOGGER.error("Error loading audio file metadata: {}".format(e))
            return
        

    def stop(self, clear_playlist=False):
        if clear_playlist:
            self.clear_playlist()
            self.current_folder = None
        PIHOME_LOGGER.info("Stopping audio")
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()  # Properly release the device
            except Exception as e:
                PIHOME_LOGGER.error(f"Error closing stream: {e}")
            finally:
                self.stream = None
        if self.process:
            self.process.terminate()
        # clear the queue
        while not self.q_in.empty():
            self.q_in.get()
        while not self.q_out.empty():
            self.q_out.get()
        self.data = None
        self.empty_buffer = True
        self.current_source = None
        self.set_state(AudioState.STOPPED)
    
    def cleanup(self):
        """Full cleanup including device release"""
        self.stop(clear_playlist=True)
        try:
            # Terminate sounddevice to release all audio resources
            import sounddevice as sd
            sd._terminate()
            PIHOME_LOGGER.info("Audio device cleanup complete")
        except Exception as e:
            PIHOME_LOGGER.error(f"Error during cleanup: {e}")

    def set_volume(self, volume, oneAsHundred=False):
        """
        Volume must be between 0 and 1
        If onAsHundred is true, then volume of 1.0 is 100
        """
        if volume > 1:
            # normalize volume between 0 and 1 
            volume = volume / 100
        if volume < 0 or volume > 1:
            PIHOME_LOGGER.error("Volume must be between 0 and 1")
            return
        if oneAsHundred and volume == 1:
            volume = 1
        self.volume = volume
        for listener in self.volume_listeners:
            listener(volume)

    def volume_up(self):
        if self.volume < 1:
            oneAsHundred = False
            if self.volume > 0.5:
                oneAsHundred = True
            self.set_volume(self.volume + 0.1, oneAsHundred=oneAsHundred)

    def volume_down(self):
        if self.volume > 0:
            self.set_volume(self.volume - 0.1)

    def next(self):
        if self.queue_pos < len(self.queue):
            self.queue_pos += 1
            self.play(self.queue[self.queue_pos], reset_playlist=False)
        else:
            self.stop()

    def prev(self):
        if self.queue_pos > 0:
            self.queue_pos -= 1
            self.play(self.queue[self.queue_pos], reset_playlist=False)

    def clear_playlist(self):
        self.queue = []
        self.queue_pos = 0

    def add_to_playlist(self, url):
        self.queue.append(url)

    def pop_playlist(self, index=0):
        return self.queue.pop(index)

    def run_youtubedl(self, url):
        # arguments to get audio 
        PIHOME_LOGGER.info("Fetching audio stream for url: {}".format(url))
        process = subprocess.Popen(['youtube-dl', 
                                    '-f', 'bestaudio/mp3/b',
                                    '--get-title',
                                    '--get-thumbnail',
                                    '--no-warnings',
                                    '-g', url], stdout=subprocess.PIPE)
        #get the output
        out, err = process.communicate()
        title = out.decode().split("\n")[0]
        thumbnail = out.decode().split("\n")[2]
        source = out.decode().split("\n")[1]
        self.title = title
        self.album_art = thumbnail
        return source


# Read audio device from configuration
# Support formats: hw:0,0 (ALSA), "Device Name", or None for auto-detect
_audio_device = CONFIG.get('audio', 'device', None)
if _audio_device == "" or _audio_device == "auto":
    _audio_device = None
AUDIO_PLAYER = AudioPlayer(device=_audio_device)
