from datetime import datetime, timezone, timedelta
from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty, DictProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.clock import Clock
from theme.theme import Theme

from util.helpers import get_app, weather
from util.tools import get_semi_transparent_gaussian_blur_png_from_color

Builder.load_file("./composites/Weather/weatherdetails.kv")

class WeatherDetails(Widget):
    theme = Theme()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY))
    blur = StringProperty(get_semi_transparent_gaussian_blur_png_from_color(theme.get_color(theme.BACKGROUND_PRIMARY), True))

    day = StringProperty("--")
    temp = StringProperty("--")
    precip = StringProperty("--")
    icon = StringProperty("")
    details = DictProperty()

    def __init__(self, details = {}, **kwargs):
        super(WeatherDetails, self).__init__(**kwargs)
        self.details = details
        self.parseDetails()
        Clock.schedule_interval(lambda _: self.parseDetails(), 1)

    
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
        time = datetime.strptime(details["startTime"], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=-5)
        self.day = datetime.strftime(time, "%I:%M %p")
        self.temp = "{}\u00B0F".format(round(details["values"]["temperature"]))
        self.precip = "{}%".format(round(details["values"]["precipitationProbability"]))

        conf = get_app().web_conf
        if conf != None:
            host = conf["host"]
            path = conf["weather_icons"]
            self.icon = "{}{}{}0.png".format(host, path, str(details["values"]["weatherCode"]))
        