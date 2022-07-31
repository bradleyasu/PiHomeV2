import subprocess
import requests
import time
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty, NumericProperty

from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.SmartLight.smartlight import SmartLight
from composites.Weather.weatherwidget import WeatherWidget
from interface.pihomescreen import PiHomeScreen
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import appmenu_open, get_app, goto_screen, weather
from util.tools import hex
from kivy.clock import Clock
from kivy.animation import Animation

Builder.load_file("./screens/Home/home.kv")

class HomeScreen(PiHomeScreen):
    theme = Theme()
    color = ColorProperty()
    image = StringProperty()
    time = StringProperty("--:-- -M")
    date = StringProperty("Saturday July 29, 2022")
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))

    logo_opacity = NumericProperty(1)

    date_time_y_offset = NumericProperty(-100)
    date_time_opacity = NumericProperty(0)

    weather_code = StringProperty("--")

    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY, 0.4)
        self.size = App.get_running_app().get_size()
        self.icon = "https://cdn.pihome.io/assets/default_home_icon.png"
        Clock.schedule_once(lambda _: self.startup_animation(), 10)
        Clock.schedule_interval(lambda _: self.run(), 1)


    def open_settings(self):
        # self.manager.current = 'settings'
        goto_screen('settings')
    
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


    def startup_animation(self):
        animation = Animation(logo_opacity = 0, t='linear', d=1)
        animation &= Animation(date_time_opacity = 1, t='out_elastic', d=1)
        animation &= Animation(date_time_y_offset = 0, t='out_elastic', d=1)
        animation.start(self)


    def run(self):
        time.ctime()
        self.time = time.strftime("%l:%M%p")
        self.date = time.strftime("%A %B %d, %Y")
        self.weather_code = str(weather().weather_code)
