from email.mime import audio
import subprocess

from composites.Reddit.redditwidget import RedditWidget
import requests
import time
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty, NumericProperty,ListProperty

from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.SmartLight.smartlight import SmartLight
from composites.Weather.weatherwidget import WeatherWidget
from interface.pihomescreen import PiHomeScreen
from listeners.ConfigurationUpdateListener import ConfigurationUpdateListener
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import appmenu_open, audio_player, get_app, goto_screen, weather
from util.tools import hex
from kivy.clock import Clock
from kivy.animation import Animation
from util.const import _SETTINGS_SCREEN, CDN_ASSET, GESTURE_SWIPE_DOWN

Builder.load_file("./screens/Home/home.kv")

class HomeScreen(PiHomeScreen):
    theme = Theme()
    color = ColorProperty()
    time = StringProperty("--:-- -M")
    date = StringProperty("Saturday July 29, 2022")
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY, 0.3))

    logo_opacity = NumericProperty(1)

    date_time_y_offset = NumericProperty(-100)
    date_time_opacity = NumericProperty(0)

    weather_code = StringProperty("--")

    is_first_run = True


    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY, 0.4)
        self.size = App.get_running_app().get_size()
        self.icon = CDN_ASSET.format("default_home_icon.png")
        # Clock.schedule_once(lambda _: self.startup_animation(), 10)
        Clock.schedule_interval(lambda _: self.run(), 1)
        self.on_gesture = self.handle_gesture

    def on_enter(self, *args):
        if self.is_first_run is True:
            audio_player().play("./assets/audio/intro/002.mp3")
            Clock.schedule_once(lambda _: self.startup_animation(), 10)
            Clock.schedule_once(lambda _: audio_player().clear_playlist(), 20)
            self.is_first_run = False
        return super().on_enter(*args)


    def open_settings(self):
        # self.manager.current = 'settings'
        goto_screen(_SETTINGS_SCREEN)

    def open_pin(self):
        self.manager.current = 'pin'


    def startup_animation(self):
        animation = Animation(logo_opacity = 0, t='linear', d=1)
        animation &= Animation(date_time_opacity = 1, t='out_elastic', d=1)
        animation &= Animation(date_time_y_offset = 0, t='out_elastic', d=1)
        animation.start(self)
        # audio_player().stop()
        # audio_player().clear_playlist()

    def run(self):
        time.ctime()
        self.time = time.strftime("%l:%M%p")
        self.date = time.strftime("%A %B %d, %Y")

        self.weather_code = str(weather().weather_code)

    def handle_gesture(self, gesture): 
        if gesture == GESTURE_SWIPE_DOWN:
            pass

    def on_rotary_pressed(self):
        get_app().wallpaper_service.shuffle()
        return False