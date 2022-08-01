import json
import os
from kivy.clock import Clock
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen
from kivy.config import ConfigParser
from kivy.uix.settings import SettingsWithSidebar
from composites.PinPad.pinpad import PinPad

from interface.pihomescreen import PiHomeScreen
from util.helpers import get_app, toast
Builder.load_file("./screens/Settings/settings.kv")

class SettingsScreen(PiHomeScreen):
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        config = ConfigParser()
        config.read('base.ini')
        config.add_callback(self.updated)
        s = SettingsWithSidebar()
        # s.register_type("pin", PinPad)
        self.icon = "https://cdn.pihome.io/assets/default_settings_icon.png"

        # Read all of the json configuations and add them to the screen
        dir = './screens/Settings/json/' 

        # Set defaults
        for file in sorted(os.listdir(dir)):
            if file.endswith(".json"):
                with open(dir+file, 'r') as f:
                    conf = json.load(f)
                    for c in conf:
                        if "section" in c and "key" in c:
                            config.adddefaultsection(c['section'])
                            config.setdefault(c['section'], c['key'], '')

                # Add configuration panel to UI
                s.add_json_panel(file.replace("_", " ").replace(".json", "").capitalize(), config, dir+file)
        
        # Override on_close event to return to the previous screen
        def on_close():
            self.manager.current = self.manager.previous()

        s.on_close = on_close
        self.add_widget(s)
    
    def updated(self, section, key, value):
        if (section == 'theme' and key == 'dark_mode'):
            toast(label="PiHome needs to be restarted for new settings to take effect")