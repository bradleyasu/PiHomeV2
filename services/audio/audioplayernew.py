import argparse
import queue
import sys
from time import sleep

import ffmpeg
import sounddevice as sd
import numpy as np
from util.phlog import PIHOME_LOGGER
from threading import Thread


class AudioPlayer:
    percent = 0
    title = "No Media"
    volume = 100.0
    is_paused = False
    playlist_pos = 0
    playlist_start = 0
    album_art = None
    queue = []
    data = None


    def __init__(self, device=None, blocksize=4096, buffersize=512):
        self.device = device
        self.blocksize = blocksize
        self.buffersize = buffersize
        self.q = queue.Queue(maxsize=self.buffersize)
        self.stream = None
        self.process = None
        self.paused = False
        self.empty_buffer = False

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
    
    def __del__(self):
        self.stop()

    def int_or_str(self, text):
        """Helper function for argument parsing."""
        try:
            return int(text)
        except ValueError:
            return text

    def callback(self, outdata, frames, time, status):
        assert frames == self.blocksize
        if status.output_underflow:
            print('Output underflow: increase blocksize?')
            raise sd.CallbackAbort
        assert not status
        try:
            data = self.q.get_nowait()
            self.data = data 
            self.empty_buffer = False
        except queue.Empty as e:
            self.empty_buffer = True
            print('Buffer is empty: increase buffersize?')
            raise sd.CallbackAbort from e
        # assert len(data) == len(outdata)
        # scaled_data = np.multiply(data_to_play, self.volume)
        if self.paused:
            data = np.zeros(len(data), dtype='float32')
        # if self.volume != 1.0:
            # data = np.multiply(data, self.volume)
        outdata[:len(data)] = data

    def play(self, url):
        self.stop()
        thread = Thread(target=self._play, args=(url,))
        thread.start()

    def _play(self, url):
        print('Getting stream information ...')

        is_local = True
        if url.startswith('http://') or url.startswith('https://'):
            is_local = False


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
            print('Opening stream ...')
            self.process = ffmpeg.input(url).output(
                'pipe:',
                format='f32le',
                acodec='pcm_f32le',
                ac=channels,
                ar=samplerate,
                loglevel='quiet',
                # reconnect=1,
                # reconnect_streamed=1,
                # reconnect_delay_max=5,
            ).run_async(pipe_stdout=True)
            self.stream = sd.RawOutputStream(samplerate=samplerate, blocksize=self.blocksize, device=self.device, channels=channels, dtype='float32', callback=self.callback)
            read_size = self.blocksize * channels * self.stream.samplesize
            print('Buffering ...')
            for _ in range(self.buffersize):
                self.q.put_nowait(self.process.stdout.read(read_size))
            print('Starting Playback ...')
            with self.stream:
                timeout = self.blocksize * self.buffersize / samplerate
                code =self.process.poll()
                while code is None and not self.empty_buffer:
                    while True:
                        d = self.process.stdout.read(read_size)
                        if not d:
                            break
                        self.q.put(d, timeout=timeout)
                print('End of stream: ', code)
                self.q.empty()
        except KeyboardInterrupt:
            PIHOME_LOGGER.info('Interrupted by user')
            return
        except queue.Full:
            # A timeout occurred, i.e. there was an error in the callback
            PIHOME_LOGGER.error('Error: Buffer is full')
            return
        except (ConnectionResetError, ConnectionAbortedError, TimeoutError) as e:
            PIHOME_LOGGER.error("Connection Error")
        except Exception as e:
            PIHOME_LOGGER.error("Other Error")
            return

    def stop(self):
        if self.stream:
            self.stream.stop()
        if self.process:
            self.process.terminate()

    def set_volume(self, volume):
        volume = volume / 100.0
        if self.stream:
            self.stream.volume = volume

    def volume_up(self):
        if self.stream:
            self.stream.volume = self.stream.volume + 0.1
        
    def volume_down(self):
        if self.stream:
            self.stream.volume = self.stream.volume - 0.1
        

# Test the AudioPlayer

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio Player")
    parser.add_argument('url', metavar='URL', help='stream URL')
    parser.add_argument('-d', '--device', type=int, help='output device (numeric ID or substring)')
    parser.add_argument('-b', '--blocksize', type=int, default=1024, help='block size (default: %(default)s)')
    parser.add_argument('-q', '--buffersize', type=int, default=20, help='number of blocks used for buffering (default: %(default)s)')
    args = parser.parse_args()

    player = AudioPlayer(args.device, args.blocksize, args.buffersize)
    player.play(args.url)


AUDIO_PLAYER = AudioPlayer()