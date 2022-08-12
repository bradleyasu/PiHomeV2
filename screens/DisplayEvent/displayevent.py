from kivy.lang import Builder
from interface.pihomescreen import PiHomeScreen
from util.helpers import goto_screen
from util.tools import hex
from kivy.clock import Clock
from kivy.properties import ColorProperty, StringProperty

Builder.load_file("./screens/DisplayEvent/displayevent.kv")

class DisplayEvent(PiHomeScreen):
    background = ColorProperty((0,0,0,0.9))
    title = StringProperty("<title>")
    message = StringProperty("<message>")
    image = StringProperty("")
    def __init__(self, **kwargs):
        super(DisplayEvent, self).__init__(**kwargs)

    def set_background(self, background):
        self.background = hex(background, 1)
  
    def set_timeout(self, seconds, screen):
        Clock.schedule_once(lambda _: goto_screen(screen), int(seconds))