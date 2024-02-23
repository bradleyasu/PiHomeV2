from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,BooleanProperty, NumericProperty, ListProperty
from networking.poller import POLLER
from theme.theme import Theme

from interface.pihomescreen import PiHomeScreen
from util.const import CDN_ASSET
from util.tools import hex
from kivy.animation import Animation
from kivy.graphics import Line, Rectangle, Ellipse, Color
from kivy.clock import Clock

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

        # Every 30 minutes
        POLLER.register_api(self.SEVEN_SPRINGS, 60 * 30, lambda json: self.update(json))

    def update(self, payload):
        self.lifts_open = payload["OpenLifts"]
        self.lifts_total = payload["TotalLifts"]
        self.current_temp = payload["CurrentTempStandard"]
        self.high_temp = payload["HighTempStandard"]
        self.low_temp = payload["LowTempStandard"]
        self.in_snow = payload["SnowReportSections"][0]["Depth"]["Inches"]
        self.weather = payload["WeatherShortDescription"]