from mplayer import Player
from .mpv import MPV

from util.const import TEMP_DIR

class AudioPlayer:
    def __init__(self, **kwargs):
        super(AudioPlayer, self).__init__(**kwargs)
        # self.player = Player()
        self.player = MPV(ytdl=True, vid=False)

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