import datetime
from kivy.lang import Builder
from kivy.metrics import dp

from interface.pihomescreen import PiHomeScreen
from screens.NewYearsEve.countdown import Countdown
from screens.NewYearsEve.fireworks import Fireworks
from util.tools import hex
from kivy.animation import Animation

Builder.load_file("./screens/NewYearsEve/newyearseve.kv")

class NewYearsEveScreen(PiHomeScreen):
    fireworks = None
    countdown = None
    def __init__(self, **kwargs):
        super(NewYearsEveScreen, self).__init__(**kwargs)

    
    def on_enter(self, *args):
        self.start()
        return super().on_enter(*args)

    def on_leave(self, *args):
        self.stop()
        return super().on_leave(*args)

    def calculate_seconds_to_new_year(self):
        new_years = datetime.datetime(datetime.datetime.now().year + 1, 1, 1)
        now = datetime.datetime.now()
        delta = new_years - now
        return delta.seconds

    def start(self):
        self.fireworks = Fireworks();
        self.countdown = Countdown(self.calculate_seconds_to_new_year(), "Happy New Year!")
        # center countdown on screen
        self.add_widget(self.fireworks)
        self.add_widget(self.countdown)
        self.fireworks.start_fireworks()
        self.countdown.start_countdown()

    def stop(self):
        self.fireworks.stop_fireworks()
        self.countdown.stop_countdown()
        self.remove_widget(self.fireworks)
        self.remove_widget(self.countdown)
        self.fireworks = None