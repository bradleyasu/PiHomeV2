from kivy.lang import Builder
from components.Image.networkimage import BLANK_IMAGE
from interface.gesturewidget import GestureWidget
from services.qr.qr import QR
from theme.color import Color
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.animation import Animation
from kivy.clock import Clock
from util.const import GESTURE_SWIPE_DOWN
from util.helpers import audio_player
from util.tools import hex

Builder.load_file("./components/Slider/slidecontrol.kv")

class SlideControl(GestureWidget):

    theme = Theme()
    background_color = ColorProperty(hex(Color.DARK_SEAFOAM_700, 0.1))
    active_color = ColorProperty(Color.DARK_SEAFOAM_700)
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    text_color_secondary = ColorProperty(theme.get_color(theme.TEXT_SECONDARY))
    label_opacity = NumericProperty(0)


    level = NumericProperty(100)
    touching = False
    min = 0
    max = 100

    def __init__(self, min = 0, max = 100, **kwargs):
        super(SlideControl, self).__init__(**kwargs)
        self.listeners = []
        self.min = min
        self.max = max

    def set_value(self, value):
        if value > self.max:
            value = self.max
        if value < self.min:
            value = self.min
        self.level = value
        self.on_change(self.level)

    def on_change(self, value):
        for listener in self.listeners:
            listener(value)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            height = (self.height)
            position = (touch.y - self.y)
            self.level = position/height * 100.0
            self.on_change(self.level)
        return False
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.touching = True
            self.label_opacity = 1

    def on_touch_up(self, touch):
        self.label_opacity = 0
        if self.collide_point(*touch.pos):
            self.touching = False

    def add_listener(self, listener):
        self.listeners.append(listener)
    

        