
import os
from kivy.lang import Builder
from kivy.properties import StringProperty
from interface.pihomescreen import PiHomeScreen
from util.const import CDN_ASSET
from util.helpers import get_config, audio_player, toast

from kivy.config import Config

from util.tools import download_image_to_temp


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
        self.audio_source = get_config().get('lofi', 'audio', 'lofi girl')
        config_image = get_config().get('lofi', 'image', "")
        if not self.audio_source.startswith("http"):
            self.audio_source = "ytdl://ytsearch5:" + self.audio_source

        if config_image == "":
            self.image = "./screens/Lofi/lofi.gif"
        else:
            self.image = download_image_to_temp(config_image).name

        audio_player().play(self.audio_source)
        toast("Searching for streams, this may take up to 20 seconds...", timeout=10);
        return super().on_enter(*args)

    def on_leave(self, *args):
        audio_player().stop()
        self.reset()
        self.image = ""
        return super().on_leave(*args)