from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import AsyncImage  
from kivy.uix.label import Label
from theme.theme import Theme
from kivy.properties import ColorProperty, BooleanProperty, NumericProperty, StringProperty, ObjectProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.loader import Loader
from kivy.metrics import dp

Builder.load_file("./components/Image/networkimage.kv")

class NetworkImage(Widget):
    theme = Theme()

    color = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY))
    url = StringProperty()
    stretch = BooleanProperty(False)
    k_ratio = BooleanProperty(True)
    loader = None
    error = None

    def __init__(self, url = "", size=(dp(50), dp(50)), pos=(dp(10), dp(10)), enable_stretch = False, loader = None, error = None, **kwargs):
        super(NetworkImage, self).__init__(**kwargs)
        Loader.loading_image = "./assets/images/blank.png"
        self.url = url
        self.size = size
        self.pos = pos
        self.stretch = enable_stretch
        self.k_ratio = not enable_stretch
        self.loader = loader
        self.error = error
        

    def set_stretch(self, enable_stretch):
        self.stretch = enable_stretch
        self.k_ratio = not enable_stretch


    def on_error(self, a = None, b = None):
        if self.error is not None:
            self.url = self.error
    
    def on_load(self):
        if self.loader is not None:
            self.url = self.loader


