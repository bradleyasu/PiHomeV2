
from interface.pihomescreen import PiHomeScreen
from kivy.properties import ColorProperty
from kivy.lang import Builder
from util.phlog import PIHOME_LOGGER
from kivy.clock import Clock
import subprocess


Builder.load_file("./screens/ShutdownScreen/shutdownscreen.kv")
class ShutdownScreen(PiHomeScreen):
    background = ColorProperty((0,0,0,1))
    text_color = ColorProperty((1,1,1,1))
    def __init__(self, **kwargs):
        super(ShutdownScreen, self).__init__(**kwargs)

    
    def on_enter(self):
        # Prevent changing screen
        PIHOME_LOGGER.warning("Shutdown screen entered and locked.  System will restart in 5 seconds.")
        self.locked = True
        # Clock.schedule_once(lambda _: subprocess.call(['sh', './update_and_restart.sh']), 5)
