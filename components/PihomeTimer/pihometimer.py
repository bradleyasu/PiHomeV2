from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.properties import StringProperty
from services.timers.timer import Timer
from kivy.clock import Clock
import time
from components.Msgbox.msgbox import MSGBOX_FACTORY

Builder.load_file("./components/PihomeTimer/pihometimer.kv")

class PiHomeTimer(Widget):

    label = StringProperty("Timer")
    time_label = StringProperty("00:00:00")

    def __init__(self, timer = None , **kwargs):
        super(PiHomeTimer, self).__init__(**kwargs)
        self.timer = timer
        # self.pos_hint = None, None
        # self.size_hint = None, None
        self.label = timer.label
        if not self.timer:
            self.timer = Timer(60)

    def start(self):
        Clock.schedule_interval(self.update, 1/60)
        self.timer.add_listener(self.destroy)
        self.timer.start()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            MSGBOX_FACTORY.show(self, "Timer", "Would you like to remove {}?".format(self.label), 0, 0, 1, self.timer.cancel)
            return True
        return super().on_touch_down(touch)

    def update(self, dt):
        if not self.timer:
            return 
        if not self.timer.is_running:
            return
        time_left = self.timer.duration - self.timer.get_elapsed_time()
        # convert time_left (seconds) into a 00:00:00 format
        formatted_time = time.strftime("%H:%M:%S", time.gmtime(time_left))
        self.time_label = formatted_time

    def destroy(self, time_left):
        Clock.unschedule(self.update)
        self.timer = None