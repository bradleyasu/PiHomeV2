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

Builder.load_file("./components/Image/networkimage.kv")

class NetworkImage(Widget):
    theme = Theme()

    color = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY))
    url = StringProperty()
    def __init__(self, url = "", size=(dp(50), dp(50)), pos=(dp(10), dp(10)), **kwargs):
        super(NetworkImage, self).__init__(**kwargs)
        self.url = url
        self.size = size
        self.pos = pos



