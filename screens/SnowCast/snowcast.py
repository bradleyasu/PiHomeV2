from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,BooleanProperty, NumericProperty, ListProperty
from theme.theme import Theme

from interface.pihomescreen import PiHomeScreen
from util.tools import hex
from kivy.animation import Animation
from kivy.graphics import Line, Rectangle, Ellipse, Color
from kivy.clock import Clock
from util.helpers import get_app, get_config, get_poller, goto_screen, toast 

Builder.load_file("./screens/SnowCast/snowcast.kv")

class SnowCast(PiHomeScreen):
    theme = Theme()
    SEVEN_SPRINGS = "https://www.7springs.com/api/PageApi/GetWeatherDataForHeader"

    lifts_open = NumericProperty(1)
    lifts_total = NumericProperty(1)
    current_temp = NumericProperty(0)
    high_temp = NumericProperty(0)
    low_temp = NumericProperty(0)
    in_snow = NumericProperty(0)
    weather = StringProperty("--")
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY, 0.3))
    def __init__(self, **kwargs):
        super(SnowCast, self).__init__(**kwargs)
        self.icon = "https://pbs.twimg.com/profile_images/1313881184087289859/-a2TI0yP_400x400.jpg"

        # Every 30 minutes
        get_poller().register_api(self.SEVEN_SPRINGS, 60 * 30, lambda json: self.update(json))

    def update(self, payload):
        self.lifts_open = payload["OpenLifts"]
        self.lifts_total = payload["TotalLifts"]
        self.current_temp = payload["CurrentTempStandard"]
        self.high_temp = payload["HighTempStandard"]
        self.low_temp = payload["LowTempStandard"]
        self.in_snow = payload["SnowReportSections"][0]["Depth"]["Inches"]
        self.weather = payload["WeatherShortDescription"]