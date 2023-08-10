
from kivy.lang import Builder
from kivy.properties import StringProperty
from interface.pihomescreen import PiHomeScreen
from util.const import CDN_ASSET
from util.helpers import get_config, audio_player

from kivy.config import Config


Builder.load_file("./screens/Lofi/lofi.kv")

class LofiScreen(PiHomeScreen):
    """
        Lofi Screen Plays Lofi Music.  Animated background coming soon.
    """

    audio_source = StringProperty()

    image = StringProperty("")

    def __init__(self, **kwargs):
        super(LofiScreen, self).__init__(**kwargs)
        self.icon = CDN_ASSET.format("lofi_app_icon.png")

    def reset(self):
        audio_player().clear_playlist()

    def on_enter(self, *args):
        self.reset()
        self.audio_source = get_config().get('lofi', 'audio', 'ytsearch5:lofi girl')
        self.image = get_config().get('lofi', 'image', CDN_ASSET.format("lofi.jpg"))

        audio_player().play(self.audio_source)
        return super().on_enter(*args)

    def on_leave(self, *args):
        self.reset()
        self.image = ""
        return super().on_leave(*args)