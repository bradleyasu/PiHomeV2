from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty

from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window

from components.Button.circlebutton import CircleButton
from components.Image.networkimage import NetworkImage
from theme.color import Color
from theme.theme import Theme
from util.helpers import get_app, get_config, get_poller, goto_screen
from util.tools import hex

Builder.load_file("./screens/Bus/bus.kv")

class BusScreen(Screen):
    theme = Theme()
    color = ColorProperty()
    image = StringProperty()

    def __init__(self, **kwargs):
        super(BusScreen, self).__init__(**kwargs)
        self.api = get_config().get('bus', 'bus_eta_url', '')
        self.key = get_config().get('bus', 'bus_eta_key', '')
        self.stop = get_config().get('bus', 'stop', '--')
        self.route = get_config().get('bus', 'route', '--')
        self.direction = get_config().get('bus', 'direction', '--')
        self.logo= get_config().get('bus', 'logo', '')

        # Register API to be polled every 200 seconds
        get_poller().register_api(self.api, self.key, 200, lambda json: self.update(json))

        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY)
        self.build()

    def build(self):
        layout = FloatLayout()
        self.grid = GridLayout(cols=1, spacing=50, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))

        homeBtn = CircleButton(text='>', size=(dp(50), dp(50)), pos=(dp(get_app().width - 70), dp(get_app().height - 70)))
        homeBtn.bind(on_release=lambda _: goto_screen('home'))
        layout.add_widget(homeBtn)

        self.logo = NetworkImage(url=self.logo, size=(dp(216), dp(112)), pos=(dp(get_app().width - 200), dp(0)))
        layout.add_widget(self.logo)

        view = ScrollView(size_hint=(1, 1), size=(get_app().width, get_app().height))
        view.add_widget(self.grid);

        layout.add_widget(view)
        self.add_widget(layout)

    def update(self, payload):
        for i in range(100):
            l = Label(text="Hello "+str(i), font_size="20sp")
            self.grid.add_widget(l)