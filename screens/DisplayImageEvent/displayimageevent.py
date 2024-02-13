from kivy.lang import Builder
from interface.pihomescreen import PiHomeScreen
from services.audio.sfx import SFX
from util.helpers import goto_screen
from util.tools import hex
from kivy.clock import Clock
from kivy.properties import ColorProperty, StringProperty, NumericProperty

Builder.load_file("./screens/DisplayImageEvent/displayimageevent.kv")

class DisplayImageEvent(PiHomeScreen):
    background = ColorProperty((hex("#000000ff")))
    image = StringProperty("")
    reload_interval = NumericProperty(0)
    def __init__(self, **kwargs):
        super(DisplayImageEvent, self).__init__(**kwargs)

    def set_timeout(self, seconds, screen):
        Clock.schedule_once(lambda _: goto_screen(screen), int(seconds))
    
    def on_leave(self, *args):
        self.image = ""
        self.reload_interval = 0
        return super().on_leave(*args)

    def on_enter(self, *args):
        SFX.play("multi_pop")
        return super().on_enter(*args)