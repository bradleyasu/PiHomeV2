from datetime import datetime, timedelta
from kivy.lang import Builder

from interface.pihomescreen import PiHomeScreen
from screens.NewYearsEve.countdown import Countdown
from screens.NewYearsEve.fireworks import Fireworks

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

    def get_newyear(self):
        current_time = datetime.now()
        next_year = current_time.year + 1
        return datetime(next_year, 1, 1, 0, 0, 0)

    def get_now_plus_20(self):
        return datetime.now() + timedelta(seconds=20)

    def start(self, debug=False):
        self.fireworks = Fireworks()
        countdown_time = self.get_now_plus_20() if debug else self.get_newyear()
        self.countdown = Countdown(
            countdown_time,
            "Happy New Year!",
            self.on_countdown_complete,
            on_phase_change=self.on_phase_change,
        )
        self.add_widget(self.fireworks)
        self.add_widget(self.countdown)
        self.fireworks.start_fireworks()
        self.countdown.start_countdown()

    def on_phase_change(self, phase):
        if self.fireworks:
            self.fireworks.set_intensity(phase)

    def on_countdown_complete(self):
        if self.fireworks:
            self.fireworks.set_intensity("celebration")

    def on_rotary_long_pressed(self):
        self.stop()
        self.start(debug=True)

    def stop(self):
        if self.fireworks:
            self.fireworks.stop_fireworks()
            self.remove_widget(self.fireworks)
            self.fireworks = None
        if self.countdown:
            self.countdown.stop_countdown()
            self.remove_widget(self.countdown)
            self.countdown = None
