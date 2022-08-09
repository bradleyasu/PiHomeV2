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

Builder.load_file("./components/Touch/longpressring.kv")

class LongPressRing(Widget):
    theme = Theme()
    color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    radius = NumericProperty(0)
    opacity = NumericProperty(0)
    def __init__(self, pos=(dp(30), dp(30)), **kwargs):
        super(LongPressRing, self).__init__(**kwargs)
        self.size = (dp(100), dp(100))
        self.pos = pos
        Clock.schedule_interval(lambda _: self.update(), 0.000001)
        
    def set_visible(self, visible, pos = (dp(10), dp(10))):
        self.pos = pos
        if visible:
            self.opacity = 1
        else:
            self.opacity = 0
            self.radius = 0

    def update(self):
        if self.opacity == 1 and self.radius < 360:
            self.radius = self.radius + 6
