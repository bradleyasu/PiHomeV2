import socket
import os
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
from interface.pihomescreen import PiHomeScreen
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import appmenu_open, get_app, goto_screen
from util.tools import hex
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.uix.slider import Slider

Builder.load_file("./screens/DevTools/devtools.kv")

class DevTools(PiHomeScreen):
    local_ip = StringProperty("0.0.0.0")
    theme = Theme()
    slider = None
    def __init__(self, **kwargs):
        super(DevTools, self).__init__(**kwargs)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        self.local_ip = s.getsockname()[0]
        s.close()
        self.build()

    
    def build(self):
        layout = FloatLayout(size=(dp(480), dp(600)), size_hint=(None, None))

        button = CircleButton(text='X', size=(dp(50), dp(50)), pos=(dp(self.width - 70), dp(self.height - 70)))
        button.stroke_color = self.theme.get_color(self.theme.ALERT_DANGER)
        button.text_color = self.theme.get_color(self.theme.ALERT_DANGER)
        button.down_color = self.theme.get_color(self.theme.ALERT_DANGER, 0.2)
        button.bind(on_release=lambda _: self.trigger_update())
        layout.add_widget(button)


        self.slider = Slider(on_touch_move=lambda x,y: self.set_brightness(self.slider.value), orientation='horizontal', min=20, max = 255, pos=(dp(self.width - 10), dp(self.height - 100)), size=(dp(40), dp(200)), step=1)
        layout.add_widget(self.slider)
        
        self.add_widget(layout)

    
    def trigger_update(self):
        subprocess.call(['sh', './update_and_restart.sh'])

    def set_brightness(self, level):
        # echo 32 > /sys/class/backlight/rpi_backlight/brightness
        subprocess.call(['sh', './set_brightness.sh', level])


  