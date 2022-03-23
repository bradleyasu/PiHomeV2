import os
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen
from kivy.config import ConfigParser
from kivy.uix.settings import SettingsWithSidebar
Builder.load_file("./screens/Settings/settings.kv")

class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        config = ConfigParser()
        config.read('base.ini')
        s = SettingsWithSidebar()

        # Read all of the json configuations and add them to the screen
        dir = './screens/Settings/json/' 
        for file in os.listdir(dir):
            if file.endswith(".json"):
                s.add_json_panel(file.replace("_", " ").replace(".json", "").capitalize(), config, dir+file)
        
        # Override on_close event to return to the previous screen
        def on_close():
            self.manager.current = self.manager.previous()

        s.on_close = on_close
        self.add_widget(s)