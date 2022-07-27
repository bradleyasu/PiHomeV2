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
from components.SmartLight.smartlight import SmartLight
from interface.pihomescreen import PiHomeScreen
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import get_app
from util.tools import hex

Builder.load_file("./screens/Home/home.kv")

class HomeScreen(PiHomeScreen):
    theme = Theme()
    color = ColorProperty()
    image = StringProperty()
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY)
        self.size = App.get_running_app().get_size()
        # self.download_image()
        self.build()

    def build(self):
        layout = FloatLayout()
        button = CircleButton(text='#', size=(dp(50), dp(50)), pos=(dp(20), dp(self.height - 70)))
        button.bind(on_release=lambda _: self.open_settings())
        layout.add_widget(button)

        button = CircleButton(text='X', size=(dp(50), dp(50)), pos=(dp(self.width - 70), dp(self.height - 70)))
        button.stroke_color = self.theme.get_color(self.theme.ALERT_DANGER)
        button.text_color = self.theme.get_color(self.theme.ALERT_DANGER)
        button.down_color = self.theme.get_color(self.theme.ALERT_DANGER, 0.2)
        button.bind(on_release=lambda _: get_app().quit())
        layout.add_widget(button)

        label = Label(text='PiHome')
        label.color = self.theme.get_color(self.theme.TEXT_PRIMARY)
        label.pos_hint = {'center_y': 0.5, 'center_x': 0.5}
        label.font_name = 'Nunito'
        label.font_size = '72sp'
        layout.add_widget(label)

        # light = SmartLight(size=(dp(200), dp(200)))
        # layout.add_widget(light)

        # light2 = SmartLight(size=(dp(200), dp(200)))
        # light2.pos = 500, 0
        # layout.add_widget(light2)


        button1 = SimpleButton(text='Test Screen', type='secondary', size=(dp(200), dp(50)), pos=(dp(10), dp(70)))
        button1.bind(on_release=lambda _: App.get_running_app().goto_screen('bus', False))
        layout.add_widget(button1)

        # button2 = SimpleButton(text='Lock Screen', type='secondary', size=(dp(200), dp(50)), pos=(dp(10), dp(70)))
        # button2.bind(on_release=lambda _: App.get_running_app().show_pinpad())
        # layout.add_widget(button2)

        self.add_widget(layout)

    def open_settings(self):
        # self.manager.current = 'settings'
        App.get_running_app().goto_screen('settings', True)
    
    def open_pin(self):
        self.manager.current = 'pin'

    def download_image(self): 
        """
        Hard coded background image download for now - just testing
        """
        img_data = requests.get('https://cdn.pixabay.com/photo/2018/08/14/13/23/ocean-3605547_1280.jpg').content
        with open('background.jpg', 'wb') as handler:
            handler.write(img_data)
        self.image = 'background.jpg'
