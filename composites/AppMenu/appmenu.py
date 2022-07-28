from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.Image.networkimage import NetworkImage
from composites.AppMenu.appicon import AppIcon
from theme.color import Color
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.uix.scrollview import ScrollView
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from util.helpers import get_app, goto_screen
from util.tools import hex
from kivy.uix.widget import Widget
from kivy.uix.button import Button

Builder.load_file("./composites/AppMenu/appmenu.kv")

class AppMenu(Widget):

    background_color = ColorProperty((0,0,0, 0.5))

    def __init__(self, screens, **kwargs):
        super(AppMenu, self).__init__(**kwargs)
        self.screens = screens
        self.build()


    def build(self):
        view = ScrollView(size_hint=(1, 1), size=(get_app().width, get_app().height))
        self.grid = GridLayout(cols=4, padding=(80, 80, 80, 80), spacing=80, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))

        view.add_widget(self.grid)
        self.add_widget(view)


    def open_app(self, key):
        get_app().set_app_menu_open(False)
        goto_screen(key)


    def reset(self):
        self.grid.clear_widgets()

    def show_apps(self):
        count = 0
        for i in self.screens:
            icon = self.screens[i].icon
            self.grid.add_widget(AppIcon(delay=count*0.100, icon=icon, label = "test", app_key = i, on_select=(lambda key: self.open_app(key))))
            count += 1