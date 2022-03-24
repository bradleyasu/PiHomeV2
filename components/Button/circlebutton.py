from kivy.app import App
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from util.tools import hex
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget


Builder.load_file("./components/Button/circlebutton.kv")

class CircleButton(ButtonBehavior, Widget):
    text = StringProperty()
    color = ColorProperty()
    stroke_color = ColorProperty(hex('#ffffff'))
    text_color = ColorProperty(hex('#ffffff'))
    primary_color = ColorProperty(hex('#ffffff', 0))
    down_color = ColorProperty(hex('#ffffff', 0.3))
    transition_duration = NumericProperty(0.5)
    zoom = NumericProperty(0)
    def __init__(self, **kwargs):
        super(CircleButton, self).__init__(**kwargs)
        self.bind(
            state=lambda *args: self.animate_color()
        )
        self.color = self.primary_color
        Clock.schedule_once(lambda _: self.start(), 1)

    def start(self):
        animation = Animation(zoom=1, t='out_elastic', d=.5)
        animation.start(self)

    def animate_color(self):
        if self.state == 'down':
            animation = Animation(color=self.down_color, duration=self.transition_duration)
            animation &= Animation(zoom=.9, t='out_quad', d=.2)
        else:
            animation = Animation(color=self.primary_color, duration=self.transition_duration)
            animation &= Animation(zoom=1, t='out_elastic', d=.5)
        animation.start(self)

