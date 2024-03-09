import argparse
import queue
import subprocess
import sys
from time import sleep
import time

import ffmpeg
import sounddevice as sd
import numpy as np
from util.phlog import PIHOME_LOGGER
from threading import Thread


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
    percent = 100
    is_playing = False


    def __init__(self, device=None, blocksize=4096, buffersize=512):
        self.device = device
        self.blocksize = blocksize
        self.buffersize = buffersize
        self.q = queue.Queue(maxsize=self.buffersize)
        self.stream = None
        self.process = None
        self.paused = False
        self.empty_buffer = False
        if self.device is None:
            self.device = self.find_sound_device()

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

    def callback(self, outdata, frames, time, status):
        # assert frames == self.blocksize
        if status.output_underflow:
            # self.stop()
            PIHOME_LOGGER.error('Output underflow: increase blocksize?')
            outdata.fill(0)
            return
        # assert not status
        try:
            data = self.q.get_nowait()
            # data = self.q.get(timeout=0.5)
            self.data = data  # store raw data for visualizations
            data = np.frombuffer(data, dtype='float32')
            self.empty_buffer = False
        except queue.Empty as e:
            self.empty_buffer = True
            self.stop()
            PIHOME_LOGGER.error('Buffer is empty: increase buffersize?')
            return
        # assert len(data) == len(outdata)
        # scaled_data = np.multiply(data_to_play, self.volume)
        # if self.paused:
            # data = np.zeros(len(data), dtype='float32')
        # if self.volume != 1.0:
            # data = np.multiply(data, self.volume)
        if len(data) > len(outdata):
            self.empty_buffer = True
        else:
            outdata[:] = data * self.volume

    def play(self, url):
        # ensure device is found
        if self.device is None:
            self.device = self.find_sound_device()
        self.stop()
        self.empty_buffer = False
        thread = Thread(target=self._play, args=(url,))
        thread.start()

    def _play(self, url):

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
                self.q.put_nowait(self.process.stdout.read(read_size))
            PIHOME_LOGGER.info('Starting Playback {} ...'.format(url))
            with self.stream:
                timeout = self.blocksize * self.buffersize / samplerate
                code =self.process.poll()
                while code is None and not self.empty_buffer:
                    buffer_recovery_count = 0
                    while True:
                        d = self.process.stdout.read(read_size)
                        if not d:
                            break
                        try: 
                            self.q.put(d, timeout=timeout)
                        except queue.Full:
                            PIHOME_LOGGER.warn('Buffer is full.  Attempting to recover {}'.format(buffer_recovery_count))
                            time.sleep(0.1)
                            if buffer_recovery_count > 10:
                                PIHOME_LOGGER.error('Buffer recovery failed.  Stopping audio')
                                self.stop()
                                return
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
        if self.stream:
            self.stream.stop()
        if self.process:
            self.process.terminate()
        # clear the queue
        while not self.q.empty():
            self.q.get()
        self.data = None
        self.empty_buffer = True

    def set_volume(self, volume):
        """
        Volume must be between 0 and 1
        """
        if volume > 1:
            # normalize volume between 0 and 1 
            volume = volume / 100
        if volume < 0 or volume > 1:
            PIHOME_LOGGER.error("Volume must be between 0 and 1")
            return
        self.volume = volume
        for listener in self.volume_listeners:
            listener(volume)

    def volume_up(self):
        if self.volume < 1:
            self.set_volume(self.volume + 0.1)

        
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