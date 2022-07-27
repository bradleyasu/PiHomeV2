import requests
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty

from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import get_config, get_poller
from util.tools import hex

Builder.load_file("./screens/Bus/bus.kv")

class BusScreen(Screen):
    theme = Theme()
    color = ColorProperty()
    slime = ColorProperty()
    image = StringProperty()
    def __init__(self, **kwargs):
        super(BusScreen, self).__init__(**kwargs)
        api = get_config().get('bus', 'bus_eta_url', '')
        key = get_config().get('bus', 'bus_eta_key', '')

        get_poller().register_api(api, key, 60, lambda json: print(json))

        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY)
        self.slime = Color.DARK_INDIGO_500
        self.build()

    def build(self):
        layout = FloatLayout()

        button = SimpleButton(text='Go Back Home', size=(dp(200), dp(50)), pos=(dp(10), dp(10)))
        button.background_color = Color.CHARTREUSE_400
        button.foreground_color = Color.GRAY_50
        button.bind(on_release=lambda _: self.open_home())
        layout.add_widget(button)

        self.add_widget(layout)

    def open_home(self):
        self.manager.current = 'home'


