
import os
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty
from interface.pihomescreen import PiHomeScreen
from components.WheelMenu.wheelmenu import WheelMenu
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

    wheel_options = ListProperty([])


    def __init__(self, **kwargs):
        super(LofiScreen, self).__init__(**kwargs)
        self.icon = CDN_ASSET.format("lofi_app_icon.png")

        self.wheel_options = [
            {'text': 'Chill', 'callback': lambda: self.play_lofi(get_config().get('lofi', 'audio', 'lofi girl')), 'icon': './screens/Lofi/tape_b_1.png'}, 
            {'text': 'Hype', 'callback': lambda: self.play_lofi(get_config().get('lofi', 'audio_2', 'hotchip radio')), 'icon': './screens/Lofi/tape_b_2.png'}, 
            {'text': 'Cancel', 'callback': lambda: print("cancel wheel_menu"), 'icon': './screens/Lofi/tape_b_1.png'},
        ]

    def reset(self):
        audio_player().clear_playlist()

    def on_enter(self, *args):
        self.reset()
        config_image = get_config().get('lofi', 'image', "")


        if config_image == "":
            self.image = "./screens/Lofi/lofi.gif"
        else:
            self.image = download_image_to_temp(config_image).name

        self.play_lofi(get_config().get('lofi', 'audio', 'lofi girl'))
        toast("Searching for streams, this may take up to 20 seconds...", timeout=10);
        return super().on_enter(*args)

    def play_lofi(self, url):
        self.audio_source = url
        if not self.audio_source.startswith("http"):
            self.audio_source = "ytdl://ytsearch5:" + self.audio_source
        audio_player().play(self.audio_source)

    def on_leave(self, *args):
        audio_player().stop()
        self.reset()
        self.image = ""
        return super().on_leave(*args)