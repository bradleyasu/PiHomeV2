from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.properties import NumericProperty, ListProperty
from services.timers.timer import Timer
from kivy.clock import Clock
from components.PihomeTimer.pihometimer import PiHomeTimer
from services.timers.timer import Timer
from util.helpers import get_app
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

from kivy.animation import Animation
from kivy.core.audio import SoundLoader
import time

Builder.load_file("./composites/TimerDrawer/timerdrawer.kv")

class TimerDrawer(GridLayout):

    timer_widgets = ListProperty([])
    alarm = SoundLoader.load("assets/audio/notify/001.mp3")

    def __init__(self, **kwargs):
        super(TimerDrawer, self).__init__(**kwargs)
        # Center Widget at the Top of the Screen
        self.cols = 1
        self.size_hint = (None, None)
        self.size = (dp(200), dp(50))
        self.padding = (dp(50), dp(0))
        # self.pos_hint = {"top": 1}
        self.pos = (dp(get_app().width /2) - self.width /2, get_app().height - self.height)
        self.add_timer(Timer(300, "Give Bella Meds"))

    def add_timer(self, timer):
        timer_widget = PiHomeTimer(timer=timer)
        self.timer_widgets.append(timer_widget)
        self.add_widget(timer_widget)
        timer.add_listener(lambda _: self.remove_widget(timer_widget))
        timer_widget.start()

    def remove_widget(self, widget):
        self.timer_widgets.remove(widget)
        self.alarm.play()
        return super().remove_widget(widget)

    def on_timer_widgets(self, instance, value):
        self.height = dp(len(value) * 50)
        if len(value) > 0:
            self.show_drawer()
        else:
            self.height = (dp(50))
            self.hide_drawer()

    def hide_drawer(self):
        # animate the drawer off the screen
        animation = Animation(y=dp(get_app().height), duration=0.5, transition="in_back")
        animation.start(self)

    def show_drawer(self):
        #animate y pos to 0
        animation = Animation(y=dp(get_app().height + 5) - self.height, duration=0.5, transition="out_back")

        animation.start(self)


    
    