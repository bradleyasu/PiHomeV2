from kivy.lang import Builder
from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from services.audio.sfx import SFX
from util.tools import hex
from kivy.clock import Clock
from kivy.properties import ColorProperty, StringProperty

Builder.load_file("./screens/DisplayEvent/displayevent.kv")

class DisplayEvent(PiHomeScreen):
    """
    THIS SCREEN IS POORLY NAMED. It should be "displayscreen".  It is overloading the term 'event' with the 
    event architecture.  This screen is used to display a message to the user.  It is used by the DisplayEvent
    """
    background = ColorProperty((0,0,0,0.9))
    title = StringProperty("<title>")
    message = StringProperty("<message>")
    image = StringProperty("")
    def __init__(self, **kwargs):
        super(DisplayEvent, self).__init__(**kwargs)

    def set_background(self, background):
        self.background = hex(background, 1)
  
    def set_timeout(self, seconds, screen):
        # Only go_back to previous screen if the current screen is the screen that was displayed
        if PIHOME_SCREEN_MANAGER.current_screen == screen:
            Clock.schedule_once(lambda _: self.go_back(), int(seconds))

    def on_enter(self, *args):
        SFX.play("multi_pop")
        return super().on_enter(*args)
    

    def on_touch_down(self, touch):
        self.go_back()
        return super().on_touch_down(touch)