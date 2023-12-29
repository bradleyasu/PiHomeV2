from datetime import datetime
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
    is_new_year = False
    def __init__(self, **kwargs):
        super(NewYearsEveScreen, self).__init__(**kwargs)

    
    def on_enter(self, *args):
        self.start()
        return super().on_enter(*args)

    def on_leave(self, *args):
        self.stop()
        return super().on_leave(*args)

    def get_newyear(self):
        current_time = datetime.now()
        next_year = current_time.year + 1
        new_year = datetime(next_year, 1, 1, 0, 0, 0)  # New Year's Day of the next year
        return new_year

    def start(self):
        self.fireworks = Fireworks();
        self.countdown = Countdown(self.get_newyear(), "Happy New Year!", self.set_new_year)
        # center countdown on screen
        self.add_widget(self.fireworks)
        self.add_widget(self.countdown)
        self.fireworks.start_fireworks()
        self.countdown.start_countdown()

    def set_new_year(self):
        self.is_new_year = True
        self.fireworks.is_big_firework = True

    def stop(self):
        self.fireworks.stop_fireworks()
        self.countdown.stop_countdown()
        self.remove_widget(self.fireworks)
        self.remove_widget(self.countdown)
        self.fireworks = None