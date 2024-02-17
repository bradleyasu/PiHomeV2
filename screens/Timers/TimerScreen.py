import time
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from interface.pihomescreen import PiHomeScreen
from util.const import _HOME_SCREEN
from util.helpers import get_app



Builder.load_file("./screens/Timers/TimerScreen.kv")

class TimerScreen(PiHomeScreen):
    """
    TimerScreen.  This is the screen that will allow you to create new timers
    """
    timerLabel = StringProperty("00:00:00")
    seconds = NumericProperty(0)

    def __init__(self, **kwargs):
        super(TimerScreen, self).__init__(**kwargs)
  
    def on_enter(self, *args):
        super(TimerScreen, self).on_enter(*args)
        self.timerLabel = "00:00:00"

    def on_rotary_pressed(self):
        TIMER_DRAWER.create_timer(self.seconds, None)
        self.seconds = 0
        self.timerLabel = "00:00:00"
        get_app().goto_screen(_HOME_SCREEN)
    
    def on_rotary_turn(self, direction, button_pressed):
        new_seconds = self.seconds
        new_seconds += (direction * 60)
        if new_seconds < 0:
            new_seconds = 0
        self.seconds = new_seconds
        self.timerLabel = self.human_readable_time(self.seconds)
        return None

    def human_readable_time(self, seconds):
        return time.strftime("%H:%M:%S", time.gmtime(seconds))