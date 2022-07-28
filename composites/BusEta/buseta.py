from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from components.Button.circlebutton import CircleButton
from theme.color import Color
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp, sp
from util.helpers import get_app
from util.tools import hex
from kivy.uix.widget import Widget
from kivy.clock import Clock

Builder.load_file("./composites/BusEta/buseta.kv")

class BusEta(Widget):
    theme = Theme()
    route = StringProperty()
    dest = StringProperty()
    eta = StringProperty()
    stop = StringProperty()
    route_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    route_background_color = ColorProperty(theme.get_color(theme.ALERT_INFO))
    time_color = ColorProperty(theme.get_color(theme.ALERT_SUCCESS))
    danger_color = ColorProperty(theme.get_color(theme.ALERT_DANGER))
    blinkOpacity = NumericProperty(1)
    
    def __init__(self, stop = "--", route = "--", dest = "BOUND", eta = "Unknown", **kwargs):
        super(BusEta, self).__init__(**kwargs)
        self.size = (dp(get_app().width - 100), dp(200))
        self.route = route
        self.stop = stop
        self.dest = dest
        self.eta = eta
        if int(eta.split(" ")[0]) < 10:
            self.time_color = self.danger_color
            self.blink()

    def blink(self):
        animation = Animation(blinkOpacity=.1, t='in_out_cubic', d=1) + Animation(blinkOpacity=1, t='in_out_cubic', d=1)
        animation.repeat = True
        animation.start(self)