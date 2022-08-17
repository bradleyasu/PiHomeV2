from mplayer import Player
import qrcode

from util.const import TEMP_DIR

class AudioPlayer:
    def __init__(self, **kwargs):
        super(AudioPlayer, self).__init__(**kwargs)
        self.player = Player()

    def play(self, url):
        if self.player:
            self.player.loadfile(url)
        else:
            raise FileNotFoundError("{} could not be played.  The player is not initialized.")

    def stop(self):
        self.player.quit()