from kivy.app import App
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp

Builder.load_file("./components/Toast/toast.kv")

class Toast(Widget):
    theme = Theme()
    text = StringProperty()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background_color = ColorProperty(theme.get_color(theme.ALERT_INFO, 1))
    info_color = ColorProperty(theme.get_color(theme.ALERT_INFO, 1))
    warning_color = ColorProperty(theme.get_color(theme.ALERT_WARNING, 1))
    error_color = ColorProperty(theme.get_color(theme.ALERT_DANGER, 1))
    success_color = ColorProperty(theme.get_color(theme.ALERT_SUCCESS, 1))
    zoom = NumericProperty(0.8)
    opacity = NumericProperty(0)
    y_pos_offset = NumericProperty(-20)
    def __init__(self, on_reset, size = (dp(740), dp(50)), pos=(dp(30), dp(30)), **kwargs):
        super(Toast, self).__init__(**kwargs)
        self.size = size
        self.pos = pos
        self.on_reset = on_reset
        
    def pop(self, label, level = "info", timeout = 5):
        self.text = label
        if( level == "info" or level == "default"):
            self.background_color = self.info_color
        if( level == "warn" or level == "warning"):
            self.background_color = self.warning_color
        if( level == "error" or level == "danger"):
            self.background_color = self.error_color
        if( level == "success" or level == "done"):
            self.background_color = self.success_color
        Clock.schedule_once(lambda _: self.animate(), 1)
        Clock.schedule_once(lambda _: self.reset(), timeout)
        Clock.schedule_once(lambda _: self.on_reset(), timeout + 1)

    def animate(self):
        animation = Animation(y_pos_offset = 0, t='out_elastic', d=1)
        animation &= Animation(opacity = 1, t='out_elastic', d=1)
        animation &= Animation(zoom = 1, t='out_elastic', d=1)
        animation.start(self)

    def reset(self):
        animation = Animation(y_pos_offset = -20, t='out_elastic', d=1)
        animation &= Animation(opacity = 0, t='linear', d=1)
        animation &= Animation(zoom = 0.8, t='out_elastic', d=1)
        animation.start(self)
