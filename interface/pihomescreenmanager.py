import json
import os
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.screenmanager import SlideTransition
from system.rotary import ROTARY_ENCODER
from util.phlog import PIHOME_LOGGER

class PiHomeScreenManager(ScreenManager):
    screens_loaded = False
    loaded_screens = {}

    def __init__(self, **kwargs):
        super(PiHomeScreenManager, self).__init__(**kwargs)
        self.rotary_encoder = ROTARY_ENCODER
        if self.rotary_encoder.is_initialized:
            self.rotary_encoder.button_callback = lambda long_press: self._rotary_pressed(long_press)
            self.rotary_encoder.update_callback = lambda direction, pressed: self._rotary_handler(direction, pressed)


    def _rotary_handler(self, direction, pressed):
        try:
            self.current_screen.on_rotary_turn(direction, pressed)
        except AttributeError:
            pass

    def _rotary_pressed(self, long_press = False):
        try:
            if long_press is True:
                self.current_screen.on_rotary_long_pressed()
            else:
                self.current_screen.on_rotary_pressed()
        except AttributeError:
            pass
    
    def reload_all(self, payload):
        PIHOME_LOGGER.info("Reloading all screens")
        for screen in self.screens:
            screen.on_config_update(payload)

    def goto(self, screen_name):
        ### TODO Add pin check here - replace goto_screen in main.py
        self.current = screen_name

    def load_screens(self):
        """
        This function will load all screens into the screen manager dynamically.  It does this by searching 
        through all subdirectories of the ./screens/ directory and looking for a 'manifest.json' file.  The manifest
        will have metadata about the screen such as the name, the class, and the icon.  This function will then 
        load the screen into the screen manager.
        """
        if self.screens_loaded:
            return
        screen_dir = "./screens/"
        for root, dirs, files in os.walk(screen_dir):
            for file in files:
                if file == "manifest.json":
                    with open(os.path.join(root, file), "r") as manifest:
                        # read the manifest file
                        metadata = json.load(manifest)
                        # load the screen
                        screen_module = metadata["module"]
                        screen_label = metadata["label"]
                        screen_name = metadata["name"]
                        screen_id = metadata["id"]
                        screen_hidden = metadata["hidden"]
                        screen_requires_pin = metadata["requires_pin"]

                        # if there is an index, use it
                        if "index" in metadata:
                            index = metadata["index"]
                        else:
                            index = 9999

                        # dynamically import the class from the module
                        module = __import__("screens.{}".format(screen_module), fromlist=[screen_module])
                        screen = getattr(module, screen_name)(name=screen_id, label=screen_label, is_hidden=screen_hidden, requires_pin=screen_requires_pin)
                        screen.app_index = index
                        self.add_widget(screen)
                        self.loaded_screens[screen_id] = screen
                        PIHOME_LOGGER.info("Loading screen: {}".format(screen_id))
        # sort the screens by their index
        self.loaded_screens = {k: v for k, v in sorted(self.loaded_screens.items(), key=lambda item: item[1].app_index)}
        # goto the first screen in the loaded screens list
        self.goto(list(self.loaded_screens.keys())[0])
        self.screens_loaded = True

        
PIHOME_SCREEN_MANAGER = PiHomeScreenManager(transition=SlideTransition(direction="down"))