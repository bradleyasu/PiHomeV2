from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from components.Button.circlebutton import CircleButton
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

Builder.load_file("./composites/AppMenu/appmenu.kv")

class AppMenu(Widget):

    background_color = ColorProperty((0,1,0, 0.4))

    def __init__(self, **kwargs):
        super(AppMenu, self).__init__(**kwargs)
        self.build()


    def build(self):
        view = ScrollView(size_hint=(1, 1), size=(get_app().width, get_app().height))
        grid = GridLayout(cols=5, spacing=80, size_hint_y=None)

        view.add_widget(grid)
        self.add_widget(view)