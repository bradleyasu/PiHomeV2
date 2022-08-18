from mplayer import Player

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
    queue = []
    def __init__(self, **kwargs):
        super(AudioPlayer, self).__init__(**kwargs)
        # self.player = Player()
        self.player = MPV(ytdl=True, vid=False)
        self._observe('media-title', lambda value: self._set_title(value))
        self._observe('percent-pos', lambda value: self._set_percent(value))
        self._observe('volume', lambda value: self._set_volume(value))
        self._observe('core-idle', lambda value: self._set_is_playing(value))
        self._observe('playlist', lambda value: self._set_playlist(value))
        self._observe('playlist-playing-pos', lambda value: self._set_playlist_pos(value))

    def play(self, url):
        if self.player:
            # self.player.loadfile(url)
            self.player.playlist_append(url)
            if not self.is_playing:
                self.player.playlist_play_index(0)
                self.player.play()
        else:
            raise FileNotFoundError("{} could not be played.  The player is not initialized.")

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
        if self.player:
            self.player.playlist_play_index(index - self.playlist_start)

    def stop(self):
        # Terminate the current player
        # self.player.quit()
        self.player.stop()
        # Create a new one
        # self.player.spawn()

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
        self.queue = data
        # print(self.queue)
    
    def set_volume(self, volume):
        self.player._set_property("volume", volume)

    def _set_playlist_pos(self, pos):
        self.playlist_pos = pos + self.playlist_start