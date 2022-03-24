from kivy.app import App
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from util.tools import hex
from kivy.properties import ColorProperty, NumericProperty
from kivy.animation import Animation


Builder.load_file("./components/Button/circlebutton.kv")

class CircleButton(ButtonBehavior, Label):
    stroke_color = ColorProperty(hex('#ffffff'))
    text_color = ColorProperty(hex('#ffffff'))
    primary_color = ColorProperty(hex('#ffffff', 0))
    down_color = ColorProperty(hex('#ffffff', 0.3))
    transition_duration = NumericProperty(0.5)
    def __init__(self, **kwargs):
        super(CircleButton, self).__init__(**kwargs)
        self.bind(
            state=lambda *args: self.animate_color()
        )
        self.color = self.primary_color

    def animate_color(self):
        if self.state == 'down':
            animation = Animation(color=self.down_color, duration=self.transition_duration)
        else:
            animation = Animation(color=self.primary_color, duration=self.transition_duration)
        animation.start(self)