import json
import glob
import os
from kivy.clock import Clock
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen
from kivy.config import ConfigParser
from kivy.uix.settings import SettingsWithSidebar
from composites.PinPad.pinpad import PinPad

from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from services.wallpaper.wallpaper import WALLPAPER_SERVICE
from util.const import _HOME_SCREEN, CONF_FILE
Builder.load_file("./screens/Settings/settings.kv")

class SettingsScreen(PiHomeScreen):
    def __init__(self, callback = None, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        config = ConfigParser()
        config.read(CONF_FILE)
        self.config = config
        s = SettingsWithSidebar()
        s.bind(on_close=self.closed)
        self.callback = callback

        # Scan all screen manifests for embedded settings panels
        for manifest_path in sorted(glob.glob('./screens/*/manifest.json')):
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            # Skip hidden screens and those with no settings defined
            if manifest.get('hidden', False):
                continue
            if 'settings' not in manifest:
                continue

            settings_data = manifest['settings']
            label = manifest.get('settingsLabel', manifest.get('label', os.path.basename(os.path.dirname(manifest_path))))

            # Register config defaults
            for c in settings_data:
                if 'section' in c and 'key' in c:
                    config.adddefaultsection(c['section'])
                    config.setdefault(c['section'], c['key'], '')

            # Add configuration panel to UI (Kivy accepts a JSON string via data=)
            s.add_json_panel(label, config, data=json.dumps(settings_data))

        # Override on_close event to return to the previous screen
        def on_close():
            self.go_back()
            # Write config and reload all services with new values
            self.config.write()
            from util.helpers import get_app
            get_app().reload_configuration()

        s.on_close = on_close
        self.add_widget(s)

    def updated(self, section, key, value):
        self.config.write()
        if self.callback is not None:
            self.callback()

    def closed(self, settings):
        self.config.write()
        if self.callback is not None:
            self.callback()
    
    def updated(self, section, key, value):
        # toast(label="PiHome needs to be restarted for new settings to take effect")
        self.config.write()
        if self.callback is not None:
            self.callback()

    def closed(self, settings):
        self.config.write()
        if self.callback is not None:
            self.callback()
