from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import AsyncImage  
from kivy.uix.label import Label
from theme.color import Color
from theme.theme import Theme
from kivy.properties import StringProperty, BooleanProperty, NumericProperty, ColorProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp

from util.helpers import get_app
from kivy.uix.effectwidget import InvertEffect, HorizontalBlurEffect

Builder.load_file("./components/Switch/switch.kv")

class PiHomeSwitch(Widget):

    theme = Theme()
    enabled = BooleanProperty(False)
    offset = NumericProperty(0)

    border_color = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY))
    background_inactive_color = theme.get_color(theme.SWITCH_INACTIVE)
    background_active_color = theme.get_color(theme.SWITCH_ACTIVE)
    background_color = ColorProperty(theme.get_color(theme.SWITCH_INACTIVE))
    button_color = ColorProperty(theme.get_color(theme.BUTTON_PRIMARY))

    def __init__(self, size = (dp(100), dp(40)), on_change = lambda _: (), **kwargs):
        super(PiHomeSwitch, self).__init__(**kwargs)
        self.size = size
        self.on_change = on_change

    def animate_on(self):
        animation = Animation(offset = (self.width - dp(4) - (self.width / 2)), t='out_bounce', d=0.2)
        animation += Animation(background_color = self.background_active_color, t='linear', d=0.2)
        animation.start(self)

    def animate_off(self):
        animation = Animation(offset = (0), t='out_bounce', d=0.2)
        animation += Animation(background_color = self.background_inactive_color, t='linear', d=0.2)
        animation.start(self)
    
    def on_enabled(self, instance, value):
        if value:
            self.animate_on()
        else:
            self.animate_off() 

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.enabled = not self.enabled
            # self.on_change(self.enabled)
            # if self.enabled:
            #     self.animate_on()
            # else:
            #     self.animate_off()
            # return False