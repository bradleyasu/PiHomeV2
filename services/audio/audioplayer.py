from mplayer import Player

from .mpv import MPV

from util.const import TEMP_DIR

class AudioPlayer:
    percent = ""
    title = ""
    is_playing = False
    volume = 100.0
    def __init__(self, **kwargs):
        super(AudioPlayer, self).__init__(**kwargs)
        # self.player = Player()
        self.player = MPV(ytdl=True, vid=False)
        self._observe('media-title', lambda value: self._set_percent(value))
        self._observe('percent-pos', lambda value: self._set_title(value))
        self._observe('volume', lambda value: self._set_volume(value))

    def play(self, url):
        if self.player:
            # self.player.loadfile(url)
            self.player.play(url)
        else:
            raise FileNotFoundError("{} could not be played.  The player is not initialized.")

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
        self.percent = value

    def _set_title(self, title):
        self.title = title

    def _set_volume(self, volume):
        self.volume = volume
    
    def set_volume(self, volume):
        self.player._set_property("volume", volume)