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

    track_inactive_color = theme.get_color(theme.SWITCH_INACTIVE)
    track_active_color   = theme.get_color(theme.SWITCH_ACTIVE)
    track_color  = ColorProperty(theme.get_color(theme.SWITCH_INACTIVE))
    thumb_color  = ColorProperty([1, 1, 1, 1])

    def __init__(self, size=(dp(50), dp(28)), on_change=lambda _: (), **kwargs):
        super(PiHomeSwitch, self).__init__(**kwargs)
        self.size = size
        self.on_change = on_change
        # start thumb at left inset
        self.offset = dp(3)

    def _thumb_on_target(self):
        return self.width - (self.height - dp(6)) - dp(3)

    def animate_on(self):
        anim = (
            Animation(offset=self._thumb_on_target(), t='out_back', d=0.25)
            & Animation(track_color=self.track_active_color, t='out_quad', d=0.2)
        )
        anim.start(self)

    def animate_off(self):
        anim = (
            Animation(offset=dp(3), t='out_back', d=0.25)
            & Animation(track_color=self.track_inactive_color, t='out_quad', d=0.2)
        )
        anim.start(self)

    def on_enabled(self, instance, value):
        if value:
            self.animate_on()
        else:
            self.animate_off()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.enabled = not self.enabled