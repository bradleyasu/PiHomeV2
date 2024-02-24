import os
import pickle
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.properties import NumericProperty, ListProperty
from services.audio.sfx import SFX
from services.timers.timer import Timer
from kivy.clock import Clock
from components.PihomeTimer.pihometimer import PiHomeTimer
from services.timers.timer import Timer
from util.helpers import get_app
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

from kivy.animation import Animation
import time

from util.phlog import PIHOME_LOGGER

Builder.load_file("./composites/TimerDrawer/timerdrawer.kv")

class TimerDrawer(GridLayout):

    cache_file = "timers.pihome"
    timer_widgets = ListProperty([])

    def __init__(self, **kwargs):
        super(TimerDrawer, self).__init__(**kwargs)
        # Center Widget at the Top of the Screen
        self.cols = 1
        self.size_hint = (None, None)
        self.size = (dp(200), dp(50))
        self.padding = (dp(50), 0)
        # self.pos_hint = {"top": 1}
        # self.pos = (dp(get_app().width /2) - self.width /2, dp(get_app().height))
        self.pos = dp(200), dp(-200)
        self.in_position = False
        # self.add_timer(Timer(30, "Give Bella Meds"))

    
    def on_parent(self, instance, value):
        try: 
            self.deserialize()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error deserializing timers: {e}")

    def serialize(self):
        # Serialize the timer_widgets to external timers.pihome file
        timers = []
        for timer_widget in self.timer_widgets:
            timers.append(timer_widget.timer.to_dict())

        with open(self.cache_file, 'wb') as file:
            pickle.dump(timers, file)
        
        PIHOME_LOGGER.info(f"Serialized {len(self.timer_widgets)} timers to {self.cache_file}")

    def deserialize(self):
        # Deserialize the timer_widgets from external timers.pihome file
        if not os.path.exists(self.cache_file):
            return
        
        timers = []
        with open(self.cache_file, 'rb') as file:
            timers = pickle.load(file)

        for timer_dict in timers:
            start_time = timer_dict["start_time"]
            duration = timer_dict["duration"]
            if start_time + duration < time.time():
                continue
            new_duration = duration - (time.time() - start_time)
            timer = Timer(new_duration, timer_dict["label"], timer_dict["on_complete"])
            self.add_timer(timer)

        
        PIHOME_LOGGER.info(f"Deserialized {len(self.timer_widgets)} timers from {self.cache_file}")


    def add_timer(self, timer):
        if self.in_position is False:
            self.pos = (dp(get_app().width /2) - self.width /2, dp(get_app().height))
        
        timer_widget = PiHomeTimer(timer=timer)
        self.timer_widgets.append(timer_widget)
        self.add_widget(timer_widget)
        timer.add_listener(lambda _: self.remove_widget(timer_widget))
        timer_widget.start()
        try:
            self.serialize()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error serializing timers: {e}")

    def create_timer(self, duration, label, on_complete = None):
        timer = Timer(duration, label, on_complete)
        self.add_timer(timer)
        SFX.play("pop")

    def remove_widget(self, widget):
        self.timer_widgets.remove(widget)
        SFX.play("success")
        try:
            self.serialize()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error serializing timers: {e}")
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


TIMER_DRAWER = TimerDrawer() 
    