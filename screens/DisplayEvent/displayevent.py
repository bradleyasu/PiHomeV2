import socket
import os
import subprocess
import requests
import time
from kivy.lang import Builder
from interface.pihomescreen import PiHomeScreen
from kivy.properties import ColorProperty, NumericProperty, StringProperty

Builder.load_file("./screens/DisplayEvent/displayevent.kv")

class DisplayEvent(PiHomeScreen):
    background = ColorProperty((0,0,0,0.9))
    title = StringProperty("<title>")
    message = StringProperty("<message>")
    image = StringProperty("")
    def __init__(self, **kwargs):
        super(DisplayEvent, self).__init__(**kwargs)

  