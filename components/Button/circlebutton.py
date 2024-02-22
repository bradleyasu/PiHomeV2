from kivy.app import App
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp

Builder.load_file("./components/Button/circlebutton.kv")

class CircleButton(ButtonBehavior, Widget):
    theme = Theme()
    text = StringProperty()
    custom_font = StringProperty("Nunito")
    color = ColorProperty()
    font_size = NumericProperty('28sp')
    stroke_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    primary_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY, 0))
    down_color = ColorProperty(theme.get_color(theme.TEXT_SECONDARY, 0.3))
    stroke_width = NumericProperty(1.)
    transition_duration = NumericProperty(0.5)
    zoom = NumericProperty(1)
    def __init__(self, size = (dp(50), dp(50)), **kwargs):
        super(CircleButton, self).__init__(**kwargs)
        self.bind(
            state=lambda *args: self.animate_color()
        )
        self.color = self.primary_color
        self.size = size
        Clock.schedule_once(lambda _: self.start(), 1)

    def start(self):
        animation = Animation(zoom=1, t='out_elastic', d=.5)
        animation.start(self)
    
    def animate_color(self):
        if self.state == 'down':
            animation = Animation(color=self.down_color, duration=0.2)
            # animation &= Animation(zoom=.9, t='out_quad', d=.2)
        else:
            animation = Animation(color=self.primary_color, duration=1)
            # animation &= Animation(zoom=1, t='out_elastic', d=.5)
        animation.start(self)

