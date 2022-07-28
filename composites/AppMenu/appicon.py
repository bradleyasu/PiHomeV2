from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from numpy import spacing
from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.Image.networkimage import NetworkImage
from theme.color import Color
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.uix.scrollview import ScrollView
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from util.helpers import get_app
from util.tools import hex
from kivy.uix.widget import Widget
from kivy.uix.button import Button

Builder.load_file("./composites/AppMenu/AppIcon.kv")

class AppIcon(Widget):

    background_color = ColorProperty((0,1, 0, 0.1))


    icon = StringProperty()
    def __init__(self, icon, label, app_key, on_select, size=(dp(100), dp(100)), **kwargs):
        super(AppIcon, self).__init__(**kwargs)
        self.icon = icon
        self.label = label
        self.app_key = app_key
        self.on_select = on_select
        self.size = size



    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.on_select(self.app_key)
            return False