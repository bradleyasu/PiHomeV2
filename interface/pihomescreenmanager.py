from kivy.uix.screenmanager import ScreenManager
from system.rotary import ROTARY_ENCODER
from util.helpers import info

class PiHomeScreenManager(ScreenManager):

    def __init__(self, **kwargs):
        super(PiHomeScreenManager, self).__init__(**kwargs)
        self.rotary_encoder = ROTARY_ENCODER
        if self.rotary_encoder.is_initialized:
            self.rotary_encoder.button_callback = lambda _: self._rotary_pressed()
            self.rotary_encoder.update_callback = lambda direction: self._rotary_handler(direction)


    def _rotary_handler(self, direction):
        try:
            self.current_screen.on_rotary_turn(direction)
        except AttributeError:
            pass

    def _rotary_pressed(self):
        try:
            self.current_screen.on_rotary_pressed()
        except AttributeError:
            pass
    
    def reload_all(self, payload):
        info("Reloading all screens")
        for screen in self.screens:
            screen.on_config_update(payload)