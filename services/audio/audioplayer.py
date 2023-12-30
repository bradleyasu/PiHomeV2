import asyncio
import os
import time

from util.helpers import toast

from .mpv import MPV

from util.const import TEMP_DIR

class AudioPlayer:
    percent = 0
    title = "No Media"
    is_playing = False
    volume = 100.0
    is_paused = False
    playlist_pos = 0
    playlist_start = 0
    album_art = ""
    queue = []
    vol_delta = 10
    last_vol_up_time = 0
    last_vol_down_time = 0

    def __init__(self, **kwargs):
        super(AudioPlayer, self).__init__(**kwargs)
        # self.player = Player()
        self.player = MPV(ytdl=True, vid=False)
        self._observe('media-title', lambda value: self._set_title(value))
        self._observe('percent-pos', lambda value: self._set_percent(value))
        self._observe('volume', lambda value: self._set_volume(value))
        self._observe('core-idle', lambda value: self._set_is_playing(value))
        self._observe('playlist', lambda value: self._set_playlist(value))
        self._observe('playlist-pos', lambda value: self._set_playlist_pos(value))

    def play(self, url):
        if url.startswith("folder://"):
            # self.parseFolder(url)
            asyncio.run(self.parseFolder(url))
        elif self.player:
            if self.is_playing:
                self.queue_next(url)
                print("queueing", url)
            else:
                self.player.loadfile(url)
                print("playing", url)
                # self.player.play()
        else:
            raise FileNotFoundError("{} could not be played.  The player is not initialized.")

    '''
    Iterate over each file in the folder and call play on each file
    '''
    async def parseFolder(self, url):
        folder = url.replace("folder://", "")
        count = 0
        self.player.playlist_clear()
        for file in os.listdir(folder):
            if count == 0:
                self.player.loadfile(os.path.join(folder, file), 'append-play')
            else:
                self.player.playlist_append(os.path.join(folder, file))
            count = count + 1

    def queue_next(self, url):
        if self.player:
            self.player.playlist_append(url)

    def toggle_play(self):
        if self.player:
            self.player.command("cycle", "pause")

    def next(self):
        if self.player:
            self.player.command("playlist-next")

    def prev(self):
        if self.player:
            self.player.command("playlist-prev")

    def playlist_play_index(self, index):
        qIdx = (index - self.playlist_start)
        try:
            if self.player:
                # self.player.playlist_play_index(index - self.playlist_start)
                self.player.command("playlist-play-index", str(index - self.playlist_start))
        except Exception as e:
            toast("Could not play selected queue index: {}".format(qIdx), "error")
            print(e)

    def stop(self):
        # Terminate the current player
        # self.player.quit()
        self.player.stop()
        # Create a new one
        # self.player.spawn()

    def clear_playlist(self):
        if self.player:
            self.queue.clear()
            self.player.playlist_clear()

    def _observe(self, observer_key, action):
        @self.player.property_observer(observer_key)
        def obac(key, value):
            action(value)

    def _set_percent(self, value):
        if value:
            self.percent = value
        else:
            self.percent = 0

    def _set_title(self, title):
        if title:
            self.title = title
        else:
            self.title = "No Media"

    def _set_volume(self, volume):
        if volume:
            self.volume = volume

    def _set_is_playing(self, is_playing):
        if is_playing:
            self.is_playing = False
        else:
            self.is_playing = True

    def _set_playlist(self, data):
        try:
            self.playlist_start = int(data[0]["id"])
        except:
            pass
        self.queue.clear()
        self.queue = data
    
    def set_volume(self, volume):
        self.player._set_property("volume", volume)

    def volume_up(self):
        now = time.time()
        if now - self.last_vol_down_time < 1:
            return
        self.last_vol_up_time = now
        if self.volume < 100 - self.vol_delta:
            self.player._set_property("volume", self.volume + self.vol_delta)
        if self.volume < 100:
            self.player._set_property("volume", self.volume + 1)

    def volume_down(self):
        now = time.time()
        if now - self.last_vol_up_time < 1:
            return
        self.last_vol_down_time = now
        if self.volume > self.vol_delta:
            self.player._set_property("volume", self.volume - self.vol_delta)
        elif self.volume > 0:
            self.player._set_property("volume", self.volume - 1)

    def _set_playlist_pos(self, pos):
        if pos:
            self.playlist_pos = pos + self.playlist_start