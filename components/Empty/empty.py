from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import AsyncImage  
from kivy.uix.label import Label
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp

from util.helpers import get_app

Builder.load_file("./components/Empty/empty.kv")

class Empty(Widget):

    message = StringProperty()
    def __init__(self, message = "Empty State", size = (800, 480), **kwargs):
        super(Empty, self).__init__(**kwargs)
        self.message = message
        self.size = size
        



