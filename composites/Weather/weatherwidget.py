from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty, NumericProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.clock import Clock

Builder.load_file("./composites/Weather/weatherwidget.kv")

class WeatherWidget(Widget):

    background_color = ColorProperty((0,1, 0, 0))
    icon = StringProperty("")

    def __init__(self, size=(dp(100), dp(50)), pos=(dp(0), dp(0)), delay = 0, **kwargs):
        super(WeatherWidget, self).__init__(**kwargs)
        self.size = size
        self.pos = pos
        self.icon = "https://files.readme.io/c3d2596-weather_icon_small_ic_mostly_clear3x.png"
        # Clock.schedule_once(lambda _: self.animate(), delay)