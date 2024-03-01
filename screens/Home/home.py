from email.mime import audio
import subprocess
from components.Slider.slidecontrol import SlideControl

from composites.Reddit.redditwidget import RedditWidget
import requests
import time
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty, NumericProperty,ListProperty, BooleanProperty

from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.SmartLight.smartlight import SmartLight
from composites.Weather.weatherwidget import WeatherWidget
from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from listeners.ConfigurationUpdateListener import ConfigurationUpdateListener
from services.audio.audioplayer import AUDIO_PLAYER
from services.audio.sfx import SFX
from services.wallpaper.wallpaper import WALLPAPER_SERVICE
from services.weather.weather import WEATHER
from system.brightness import get_brightness, set_brightness
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import appmenu_open, get_app
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
    brightness_slider = None


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
            Clock.schedule_once(lambda _: self.startup_animation(), 10)
            self.is_first_run = False
            #SFX.play("notify")

        return super().on_enter(*args)

    def change_brightness(self, value):
        set_brightness(value)

    def open_settings(self):
        # self.manager.current = 'settings'
        PIHOME_SCREEN_MANAGER.goto(_SETTINGS_SCREEN)

    def open_pin(self):
        self.manager.current = 'pin'

    def startup_animation(self):
        SFX.play("startup")
        animation = Animation(logo_opacity = 0, t='linear', d=1)
        animation &= Animation(date_time_opacity = 1, t='out_elastic', d=1)
        animation &= Animation(date_time_y_offset = 0, t='out_elastic', d=1)
        animation.start(self)
        # AUDIO_PLAYER.stop()
        # AUDIO_PLAYER.clear_playlist()

    def run(self):
        time.ctime()
        self.time = time.strftime("%l:%M%p")
        self.date = time.strftime("%A %B %d, %Y")

        self.weather_code = str(WEATHER.weather_code)

    def handle_gesture(self, gesture): 
        if gesture == GESTURE_SWIPE_DOWN:
            pass

    def on_rotary_long_pressed(self):
        self.toggle_controls()

    def on_rotary_pressed(self):
        WALLPAPER_SERVICE.shuffle()

    def on_rotary_turn(self, direction, pressed):
        if self.brightness_slider is None:
            return super().on_rotary_turn(direction, pressed)
        if direction == 1:
            self.brightness_slider.set_value(self.brightness_slider.level + 5)
        elif direction == -1:
            self.brightness_slider.set_value(self.brightness_slider.level - 5)

    def toggle_controls(self):
        if self.brightness_slider is None:
            self.brightness_slider = SlideControl(size=(dp(20), dp(200)), pos=(dp(get_app().width -30), dp(10)))
            self.brightness_slider.add_listener(lambda value: self.change_brightness(value))
            self.brightness_slider.background_color = hex(Color.CHARTREUSE_600, 0.1)
            self.brightness_slider.active_color = hex(Color.DARK_CHARTREUSE_700)
            self.brightness_slider.level = get_brightness()
            self.add_widget(self.brightness_slider)
        else:
            self.remove_widget(self.brightness_slider)
            self.brightness_slider = None