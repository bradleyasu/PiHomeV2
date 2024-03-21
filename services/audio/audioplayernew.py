import argparse
import queue
import subprocess
import sys
from time import sleep
import time

import ffmpeg
from services.wallpaper.wallpaper import WALLPAPER_SERVICE
import sounddevice as sd
import numpy as np
from util.phlog import PIHOME_LOGGER
from threading import Thread
from services.audio.audioplayer import AudioPlayer as OLD_AUDIO_PLAYER


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
    playlist_pos = 0
    playlist_start = 0
    album_art = None
    queue = []
    data = None
    volume_listeners = []
    state_listeners = []
    percent = 100
    is_playing = False
    current_state = AudioState.STOPPED


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
        if self.device is None:
            self.device = self.find_sound_device()

        # start audio procesing thread
        self.thread = Thread(target=self.audio_processing_thread)
        self.thread.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
    
    def __del__(self):
        self.stop()

    def find_sound_device(self):
        PIHOME_LOGGER.info("Finding sound device")
        sd._terminate()
        sd._initialize()
        devices = sd.query_devices()
        for device in devices:
            if device['max_output_channels'] > 0:
                PIHOME_LOGGER.info(f"Found sound device: {device['name']}")
                return device['name']
        PIHOME_LOGGER.error("NO SOUND DEVICE FOUND!")
        self.log_sound_devices()
        return None
    
    def log_sound_devices(self):
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

    def set_state(self, state):
        self.current_state = state
        self.notify_state_listeners(state)

    def audio_processing_thread(self):
        PIHOME_LOGGER.info("Starting audio processing thread")
        while True:
            try:
                data = self.q_in.get_nowait()
                # self.data = data
            except queue.Empty:
                continue

            # Perform the expensive operations here
            data = np.frombuffer(data, dtype='float32')
            self.q_out.put(data)
            # vol_data = data * self.volume
            # self.q_out.put(vol_data)
            sleep(0.01)
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
        outdata[:] = vol_data.tobytes()

    def play(self, url):
        # ensure device is found
        if self.device is None:
            self.device = self.find_sound_device()
        self.stop()
        self.empty_buffer = False
        thread = Thread(target=self._play, args=(url,))
        thread.start()

    def _play(self, url):
        WALLPAPER_SERVICE.paused = True
        self.set_state(AudioState.FETCHING)
        is_local = True
        if url.startswith('http://') or url.startswith('https://'):
            is_local = False
            url = self.run_youtubedl(url)


        if not is_local:
            try:
                info = ffmpeg.probe(url)
            except ffmpeg.Error as e:
                PIHOME_LOGGER.error(e)
                PIHOME_LOGGER.error(e.stderr)
                return

            streams = info.get('streams', [])
            if len(streams) != 1:
                PIHOME_LOGGER.error('There must be exactly one stream available')
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
                self.stop()
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

    def stop(self):
        PIHOME_LOGGER.info("Stopping audio")
        WALLPAPER_SERVICE.paused = False
        if self.stream:
            self.stream.stop()
        if self.process:
            self.process.terminate()
        # clear the queue
        while not self.q_in.empty():
            self.q_in.get()
        while not self.q_out.empty():
            self.q_out.get()
        self.data = None
        self.empty_buffer = True
        self.set_state(AudioState.STOPPED)

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

    def next():
        pass

    def prev():
        pass

    def clear_playlist():
        pass

    def run_youtubedl(self, url):
        # arguments to get audio 
        PIHOME_LOGGER.info("Fetching audio stream for url: {}".format(url))
        process = subprocess.Popen(['youtube-dl', 
                                    '-f', 'bestaudio/mp3/b',
                                    '--no-warnings',
                                    '-g', url], stdout=subprocess.PIPE)
        #get the output
        out, err = process.communicate()
        return out.decode('utf-8').strip()

AUDIO_PLAYER = AudioPlayer()
# Temporary while working out kinks
# AUDIO_PLAYER = OLD_AUDIO_PLAYER()