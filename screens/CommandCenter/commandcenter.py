import os
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, ColorProperty
from interface.pihomescreen import PiHomeScreen
from screens.CommandCenter.commandbutton import CommandButton
from theme.theme import Theme
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
        Screen to provide buttons to run shell commands.  Up to 8 commands can 
        be configured in the settings screen.
    """

    theme = Theme()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background_color_prime = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY, 0.8))
    background_color_secondary = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY, 0.4))


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

    def on_exit(self, *args):
        self.grid.clear_widgets()
        return super().on_exit(*args)


    def run_command(self, button, command):
        response = execute_command(command)
        if response['return_code'] == 0:
            button.show_success()
        else:
            button.show_error()
    
    def create_button(self, index):
        icon = get_config().get("controlcenter", "cc_button_"+index+"_icon", None)
        label = get_config().get("controlcenter", "cc_button_"+index+"_label", None)
        command = get_config().get("controlcenter", "cc_button_"+index+"_command", None)
        i = label + "_ccb"
        if icon is not None and label is not None and command is not None and icon != "" and label != "" and command != "":
            self.grid.add_widget(CommandButton(delay=0.1, icon=icon, label = label, app_key = i, on_select=(lambda key: self.run_command(key, command))))

    def show_commands(self):
        for i in range(1, 8):
            self.create_button(str(i))