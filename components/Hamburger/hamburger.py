from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import AsyncImage  
from kivy.uix.label import Label
from interface.gesturewidget import GestureWidget
from theme.theme import Theme
from kivy.properties import BooleanProperty, ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp

from util.helpers import get_app

Builder.load_file("./components/Hamburger/hamburger.kv")

class Hamburger(Widget):

    top_offset = NumericProperty(0)
    bottom_offset = NumericProperty(0)
    is_open = BooleanProperty(False)
    def __init__(self, **kwargs):
        super(Hamburger, self).__init__(**kwargs)

    def on_is_open(self, instance, value):
        offset = 0
        if value == True:
            offset = 10
        animation = Animation(top_offset=dp(offset * -1), t='linear', d=0.25)
        animation &= Animation(bottom_offset=dp(offset), t='linear', d=0.25)
        animation.start(self)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.is_open = not self.is_open
            return False
