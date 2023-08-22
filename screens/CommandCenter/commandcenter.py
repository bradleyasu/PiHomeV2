import os
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty
from composites.AppMenu.appicon import AppIcon
from interface.pihomescreen import PiHomeScreen
from components.WheelMenu.wheelmenu import WheelMenu
from util.const import CDN_ASSET

from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.metrics import dp
from util.helpers import get_app, get_config
from kivy.config import Config

from util.tools import download_image_to_temp, execute_command


Builder.load_file("./screens/CommandCenter/commandcenter.kv")

class CommandCenterScreen(PiHomeScreen):
    """
        Lofi Screen Plays Lofi Music.  Animated background coming soon.
    """

    audio_source = StringProperty()

    image = StringProperty("")

    wheel_options = ListProperty([])


    def __init__(self, **kwargs):
        super(CommandCenterScreen, self).__init__(**kwargs)
        # self.icon = CDN_ASSET.format("lofi_app_icon.png")
        self.build()


    def build(self):
        view = ScrollView(size_hint=(1, 1), size=(dp(get_app().width), dp(get_app().height)))
        self.grid = GridLayout(cols=4, padding=(dp(80), dp(80), dp(80), dp(80)), spacing=(dp(80)), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))

        view.add_widget(self.grid)
        self.add_widget(view)


    def on_enter(self, *args):
        self.grid.clear_widgets()
        self.show_commands()
        return super().on_enter(*args)
    

    def create_button(self, index):
        icon = get_config().get("controlcenter", "cc_button_"+index+"_icon", None)
        label = get_config().get("controlcenter", "cc_button_"+index+"_label", None)
        command = get_config().get("controlcenter", "cc_button_"+index+"_command", None)
        i = label + "_ccb"
        if icon is not None and label is not None and command is not None and icon != "" and label != "" and command != "":
            self.grid.add_widget(AppIcon(delay=0.1, icon=icon, label = label, app_key = i, on_select=(lambda key: execute_command(command))))
            print("Added button: " + label + " with command: " + command)

    def show_commands(self):
        for i in range(1, 8):
            self.create_button(str(i))