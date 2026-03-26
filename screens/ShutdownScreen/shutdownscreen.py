
from interface.pihomescreen import PiHomeScreen
from kivy.properties import ColorProperty
from kivy.lang import Builder
from services.audio.sfx import SFX
from util.phlog import PIHOME_LOGGER
from kivy.clock import Clock
import subprocess


Builder.load_file("./screens/ShutdownScreen/shutdownscreen.kv")
class ShutdownScreen(PiHomeScreen):
    background = ColorProperty((0,0,0,1))
    text_color = ColorProperty((1,1,1,1))
    def __init__(self, **kwargs):
        super(ShutdownScreen, self).__init__(**kwargs)


    def update(self):
        try:
            subprocess.run(
                    ["sudo", "git", "-C", "/usr/local/PiHome", "pull", "--ff-only"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
        except Exception as e:
            PIHOME_LOGGER.error("Shutdown: Failed to update: {}".format(e))

    def restart(self):
        try:
            subprocess.Popen(
                ["sudo", "systemctl", "restart", "pihome"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            PIHOME_LOGGER.error("Shutdown: Restart failed: {}".format(e))

    def on_enter(self, *args):
        # Prevent changing screen
        PIHOME_LOGGER.warning("Shutdown screen entered and locked.  System will restart in 5 seconds.")
        SFX.play("shutdown")
        self.locked = True
        Clock.schedule_once(lambda _: self.update(), 5)
        Clock.schedule_once(lambda _: self.restart(), 15)
        return super().on_enter(*args)
