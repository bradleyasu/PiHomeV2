from datetime import datetime
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout



class Countdown(BoxLayout):
    dest_time = 0
    countdown_time = 0
    def __init__(self, countdown_time, message, on_timeout, **kwargs):
        super(Countdown, self).__init__(**kwargs)
        self.orientation = 'vertical'
        # calculate seconds to countdown_time
        self.dest_time = countdown_time
        self._step()
        self.message = message
        self.on_timeout = on_timeout
        self.label = Label(text=str(self.countdown_time), font_size='100sp')
        self.label.outline_width = 2
        self.label.outline_color = (0, 0, 0, 0.7)
        self.label.font_name = 'Nunito'
        self.add_widget(self.label)
        self.countdown_event = None
    
    def _step(self):
        now = datetime.now()
        time_difference = self.dest_time - now
        seconds = time_difference.total_seconds()
        rounded_seconds = round(seconds)
        self.countdown_time = rounded_seconds

    def start_countdown(self):
        self.countdown_event = Clock.schedule_interval(self.update_countdown, 1)

    def update_countdown(self, dt):
        self._step()
        self.label.text = str(self.countdown_time)
        if self.countdown_time == 0:
            self.label.text = self.message
            self.on_timeout()
            self.stop_countdown()

    def stop_countdown(self):
        if self.countdown_event:
            self.countdown_event.cancel()