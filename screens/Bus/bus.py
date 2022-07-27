import requests
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.uix.image import AsyncImage
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty

from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.Image.networkimage import NetworkImage
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import get_app, get_config, get_poller, goto_screen
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
        self.logo= get_config().get('bus', 'logo', '')

        # get_poller().register_api(api, key, 60, lambda json: print(json))

        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY)
        self.slime = Color.DARK_INDIGO_500
        self.build()

    def build(self):
        layout = FloatLayout()

        homeBtn = CircleButton(text='→', size=(dp(50), dp(50)), pos=(dp(get_app().width - 70), dp(get_app().height - 70)))
        homeBtn.bind(on_release=lambda _: goto_screen('home'))
        layout.add_widget(homeBtn)

        self.logo = NetworkImage(url=self.logo, size=(dp(216), dp(112)), pos=(dp(get_app().width - 200), dp(0)))
        layout.add_widget(self.logo)

        self.add_widget(layout)



