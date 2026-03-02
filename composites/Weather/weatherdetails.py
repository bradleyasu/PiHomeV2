from datetime import datetime, timezone, timedelta
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ColorProperty, StringProperty, DictProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.clock import Clock
from theme.theme import Theme

from util.helpers import get_app
from util.tools import get_semi_transparent_gaussian_blur_png_from_color
from services.weather.weather import WEATHER

Builder.load_file("./composites/Weather/weatherdetails.kv")

class WeatherDetails(Widget):
    theme = Theme()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY))
    blur = StringProperty(get_semi_transparent_gaussian_blur_png_from_color(theme.get_color(theme.BACKGROUND_PRIMARY), True))

    # Theme-aware card surfaces
    card_bg_color     = ColorProperty([1.0, 1.0, 1.0, 0.07] if theme.mode == 1 else [0.0, 0.0, 0.0, 0.05])
    card_border_color = ColorProperty([1.0, 1.0, 1.0, 0.04] if theme.mode == 1 else [0.0, 0.0, 0.0, 0.07])

    day = StringProperty("--")
    temp = StringProperty("--")
    precip = StringProperty("--")
    icon = StringProperty("")
    icon_fallback = StringProperty("")  # always the daytime variant; used when night icon is missing
    details = DictProperty()
    is_daily = BooleanProperty(False)

    def __init__(self, details = {}, **kwargs):
        super(WeatherDetails, self).__init__(**kwargs)
        # Re-evaluate colors at instance creation so theme mode is current
        t = Theme()
        self.text_color = t.get_color(t.TEXT_PRIMARY)
        if t.mode == 1:
            self.card_bg_color     = [1.0, 1.0, 1.0, 0.07]
            self.card_border_color = [1.0, 1.0, 1.0, 0.04]
        else:
            self.card_bg_color     = [0.0, 0.0, 0.0, 0.05]
            self.card_border_color = [0.0, 0.0, 0.0, 0.07]
        self.details = details
        self.parseDetails()
        Clock.schedule_interval(lambda _: self.parseDetails(), 1)

    def on_config_update(self, config=None):
        t = Theme()
        self.text_color = t.get_color(t.TEXT_PRIMARY)
        if t.mode == 1:
            self.card_bg_color     = [1.0, 1.0, 1.0, 0.07]
            self.card_border_color = [1.0, 1.0, 1.0, 0.04]
        else:
            self.card_bg_color     = [0.0, 0.0, 0.0, 0.05]
            self.card_border_color = [0.0, 0.0, 0.0, 0.07]

    
    def parseDetails(self):
        """
            {
               "startTime": "2022-08-02T10:00:00Z",
               "values": {
                    "humidity": 92.41,
                    "precipitationIntensity": 0.02,
                    "precipitationProbability": 15,
                    "sunriseTime": "2022-08-02T10:24:00Z",
                    "sunsetTime": "2022-08-03T00:27:00Z",
                    "temperature": 84.58,
                    "uvIndex": 8,
                    "visibility": 9.94,
                    "weatherCode": 1000,
                    "weatherCodeDay": 10000,
                    "weatherCodeNight": 10001,
                    "windDirection": 239.09,
                    "windSpeed": 9.81
            }
        """
        details = self.details
        if len(details) == 0:
            return
        slot_dt = datetime.strptime(details["startTime"], "%Y-%m-%dT%H:%M:%SZ")
        local_dt = slot_dt + timedelta(hours=-5)
        if self.is_daily:
            self.day = datetime.strftime(local_dt, "%a")
        else:
            self.day = datetime.strftime(local_dt, "%I:%M %p")
        self.temp = "{}\u00B0F".format(round(details["values"]["temperature"]))
        self.precip = "{}%".format(round(details["values"]["precipitationProbability"]))

        conf = get_app().web_conf
        if conf != None:
            host = conf["host"]
            path = conf["weather_icons"]
            day_code = 0 if WEATHER.is_currently_day(slot_dt) else 1
            self.icon = "{}{}{}{}.png".format(host, path, str(details["values"]["weatherCode"]), day_code)
            self.icon_fallback = "{}{}{}{}.png".format(host, path, str(details["values"]["weatherCode"]), 0)
        