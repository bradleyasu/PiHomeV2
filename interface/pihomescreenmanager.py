from kivy.uix.screenmanager import ScreenManager
from system.rotary import ROTARY_ENCODER
from util.phlog import PIHOME_LOGGER

class PiHomeScreenManager(ScreenManager):

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