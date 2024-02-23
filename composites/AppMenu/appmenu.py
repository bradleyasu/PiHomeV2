from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.Image.networkimage import NetworkImage
from composites.AppMenu.appicon import AppIcon
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
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

Builder.load_file("./composites/AppMenu/appmenu.kv")

class AppMenu(Widget):

    background_color = ColorProperty((0,0,0, 0.8))
    disabled = False

    def __init__(self, screens, **kwargs):
        super(AppMenu, self).__init__(**kwargs)
        self.screens = screens
        self.build()


    def build(self):
        view = ScrollView(size_hint=(1, 1), size=(dp(get_app().width), dp(get_app().height)))
        self.grid = GridLayout(cols=4, padding=(dp(80), dp(80), dp(80), dp(80)), spacing=(dp(80)), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))

        view.add_widget(self.grid)
        self.add_widget(view)
        self.view = view


    def open_app(self, key):
        if self.disabled:
            return
        get_app().set_app_menu_open(False)
        PIHOME_SCREEN_MANAGER.goto(key)


    def hide(self):
        self.opacity = 0
        # disable touch events
        self.disabled = True
        # even though the menu is hidden, touch events are still being registered
        # so we need to move the position of everything off screen
        self.pos = (0, 1000)
        self.grid.pos = (0, 1000)
        self.view.pos = (0, 1000)

    def show(self):
        # self.opacity = 1
        # enable touch events
        self.disabled = False
        # move everything back to the original position
        self.pos = (0, 0)
        self.view.pos = (0, 0)
        self.grid.pos = (0, 0)
        #bounce animate the grid back in
        anim = Animation(pos=(0, 0), t='in_expo', d=0.5)
        # anim.start(self)
        # # anim.start(self.grid)
        # # # anim.start(self.view)
        # fade in opacity
        anim = Animation(opacity=1, t='in_expo', d=0.1)
        anim.start(self)



    def reset(self):
        self.grid.clear_widgets()

    def show_apps(self):
        count = 0
        for i in self.screens:
            if not self.screens[i].is_hidden:
                icon = self.screens[i].icon
                label = self.screens[i].label
                self.grid.add_widget(AppIcon(delay=count*0.100, icon=icon, label = label, app_key = i, on_select=(lambda key: self.open_app(key))))
                count += 1