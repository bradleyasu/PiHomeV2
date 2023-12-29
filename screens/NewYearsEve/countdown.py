from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout


class Countdown(BoxLayout):
    def __init__(self, countdown_time, message, on_timeout, **kwargs):
        super(Countdown, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.countdown_time = countdown_time
        self.message = message
        self.on_timeout = on_timeout
        self.label = Label(text=str(self.countdown_time), font_size='100sp')
        self.add_widget(self.label)
        self.countdown_event = None

    def start_countdown(self):
        self.countdown_event = Clock.schedule_interval(self.update_countdown, 1)

    def update_countdown(self, dt):
        self.countdown_time -= 1
        self.label.text = str(self.countdown_time)
        if self.countdown_time == 0:
            self.label.text = self.message
            self.on_timeout()
            self.stop_countdown()

    def stop_countdown(self):
        if self.countdown_event:
            self.countdown_event.cancel()