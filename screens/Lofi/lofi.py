
import os
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty
from interface.pihomescreen import PiHomeScreen
from components.WheelMenu.wheelmenu import WheelMenu
from util.configuration import CONFIG
from util.const import CDN_ASSET
from util.helpers import audio_player, info

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
            {'text': str(CONFIG.get('lofi', 'audio_label', 'Option 1')), 'callback': lambda: self.play_lofi(CONFIG.get('lofi', 'audio', 'lofi girl')), 'icon': './screens/Lofi/tape_b_1.png'}, 
            {'text': str(CONFIG.get('lofi', 'audio_2_label', 'Option 2')), 'callback': lambda: self.play_lofi(CONFIG.get('lofi', 'audio_2', 'lofi girl')), 'icon': './screens/Lofi/tape_b_2.png'}, 
            {'text': str(CONFIG.get('lofi', 'audio_3_label', 'Option 2')), 'callback': lambda: self.play_lofi(CONFIG.get('lofi', 'audio_3', 'lofi girl')), 'icon': './screens/Lofi/tape_b_2.png'}, 
            {'text': str(CONFIG.get('lofi', 'audio_4_label', 'Option 2')), 'callback': lambda: self.play_lofi(CONFIG.get('lofi', 'audio_4', 'lofi girl')), 'icon': './screens/Lofi/tape_b_2.png'}, 
            {'text': str(CONFIG.get('lofi', 'audio_5_label', 'Option 2')), 'callback': lambda: self.play_lofi(CONFIG.get('lofi', 'audio_5', 'lofi girl')), 'icon': './screens/Lofi/tape_b_2.png'}, 
            {'text': 'Cancel', 'callback': lambda: print("cancel wheel_menu"), 'icon': './screens/Lofi/tape_b_1.png'},
        ]

    def reset(self):
        audio_player().stop()
        audio_player().clear_playlist()

    def on_enter(self, *args):
        config_image = CONFIG.get('lofi', 'image', "")


        if config_image == "":
            self.image = "./screens/Lofi/lofi.gif"
        else:
            self.image = download_image_to_temp(config_image).name

        self.play_lofi(CONFIG.get('lofi', 'audio', 'lofi girl'))
        # toast("Searching for streams, this may take up to 20 seconds...", timeout=10);
        return super().on_enter(*args)

    def play_lofi(self, url):
        self.reset()
        self.audio_source = url
        if self.audio_source.startswith("folder://"):
            self.audio_source = self.audio_source 
        elif not self.audio_source.startswith("http"):
            self.audio_source = "ytdl://ytsearch5:" + self.audio_source
        audio_player().play(self.audio_source)

    def on_leave(self, *args):
        # self.reset()
        self.image = ""
        return super().on_leave(*args)

    def on_rotary_pressed(self):
        if self.ids.wheel_menu.is_open == True:
            self.ids.wheel_menu.activate_selected((self.ids.wheel_menu.options[self.ids.wheel_menu.selected_index], self.ids.wheel_menu.selected_index))
            self.ids.wheel_menu.is_open = False
        else:
            self.ids.wheel_menu.is_open = True
            self.ids.wheel_menu.set_selected(self.wheel_options[0], 0)
        return False

    def on_rotary_turn(self, direction, pressed):
        if self.ids.wheel_menu.is_open == True:
            if direction == 1:
                if self.ids.wheel_menu.selected_index == len(self.wheel_options) - 1:
                    self.ids.wheel_menu.set_selected(self.wheel_options[0], 0)
                else:
                    self.ids.wheel_menu.set_selected(self.wheel_options[self.ids.wheel_menu.selected_index + 1], self.ids.wheel_menu.selected_index + 1)
            elif direction == -1:
                if self.ids.wheel_menu.selected_index == 0:
                    self.ids.wheel_menu.set_selected(self.wheel_options[len(self.wheel_options) - 1], len(self.wheel_options) - 1)
                else:
                    self.ids.wheel_menu.set_selected(self.wheel_options[self.ids.wheel_menu.selected_index - 1], self.ids.wheel_menu.selected_index - 1)
            return False
        else:
            return super().on_rotary_turn(direction, pressed)