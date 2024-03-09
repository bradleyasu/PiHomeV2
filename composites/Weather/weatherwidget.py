from composites.Weather.weatherdetails import WeatherDetails
from kivy.lang import Builder
from kivy.properties import Property, ColorProperty, StringProperty, NumericProperty, DictProperty, ListProperty, ObjectProperty, ReferenceListProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.clock import Clock
from services.weather.weather import WEATHER
from theme.theme import Theme

from util.helpers import get_app 
from util.phlog import PIHOME_LOGGER
from util.tools import get_semi_transparent_gaussian_blur_png_from_color

Builder.load_file("./composites/Weather/weatherwidget.kv")

class WeatherWidget(Widget):
    theme = Theme()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY))
    blur = StringProperty(get_semi_transparent_gaussian_blur_png_from_color(theme.get_color(theme.BACKGROUND_PRIMARY), True))

    background_color = ColorProperty((0,1, 0, 0))
    icon = StringProperty("")
    temp = StringProperty("--")

    uvIndex = StringProperty("--")
    windSpeed = StringProperty("--")
    precipPercent = StringProperty("--")
    humidity = StringProperty("--")
    airQuality = StringProperty("--")
    cloudCover = StringProperty("--")
    dayIcon = StringProperty("")
    nightIcon = StringProperty("")
    sunrise = StringProperty("")
    sunset = StringProperty("")
    feelsLike = StringProperty("")
    future = ListProperty([])

    overlay_opacity = NumericProperty(0)
    overlay_y_offset = NumericProperty(10)
    overlay_active = False

    is_loaded = False

    y_offset = NumericProperty(50)

    def __init__(self, size=(dp(100), dp(50)), pos=(dp(0), dp(0)), delay = 0, **kwargs):
        super(WeatherWidget, self).__init__(**kwargs)
        self.size = size
        self.pos = pos
        self.overlay_size = dp(get_app().width-40), dp(get_app().height-80)

        if(WEATHER.enabled):
            Clock.schedule_interval(lambda _: self.update(), 1)
            PIHOME_LOGGER.info("Weather is enabled.  Weather update thread will be running.")
        else: 
            PIHOME_LOGGER.warn("Weather is not enabled.  Weather update thread will not be running.")


    def on_touch_down(self, touch):
        if self.is_loaded == False:
            return False
        if self.collide_point(*touch.pos):
            if self.overlay_active == True:
                self.overlay_animate(opacity = 0, offset = 10)
            else: 
                self.overlay_animate(opacity = 1, offset = 0)
            self.overlay_active = not self.overlay_active
            return False
    
    def overlay_animate(self, opacity = 1, offset = 0):
        animation = Animation(overlay_opacity = opacity, t='linear', d=0.5)
        animation &= Animation(overlay_y_offset = offset, t='out_elastic', d=2)
        animation.start(self)

    def animate_in(self):
        animation = Animation(y_offset = 0, t='out_elastic', d=2)
        animation.start(self)

    def update(self):
        try:
            self.temp = str(round(WEATHER.temperature))
            self.uvIndex = str(WEATHER.uv_index)
            self.windSpeed = "{} MPH".format(WEATHER.wind_speed)
            self.precipPercent = "{}%".format(WEATHER.precip_propability)
            self.humidity = "{}%".format(WEATHER.humidity)
            #self.airQuality = WEATHER.epa_air_lookup[WEATHER.epa_air_quality]
            self.airQuality = "NA"
            self.sunrise = "{}".format(WEATHER.sunrise_time)
            self.sunset = "{}".format(WEATHER.sunset_time)
            self.feelsLike = "{}".format(WEATHER.feels_like)
            self.cloudCover = "{}%".format(WEATHER.cloud_cover)
            self.future = WEATHER.future
            self.day = WEATHER.future[1]


            conf = get_app().web_conf
            if conf != None:
                host = conf["host"]
                path = conf["weather_icons"]
                day_code = 0
                if WEATHER.is_currently_day() == False:
                    day_code = 1
                self.icon = "{}{}{}{}.png".format(host, path, str(WEATHER.weather_code), str(day_code))
                self.dayIcon = "{}{}{}.png".format(host, path, str(WEATHER.weather_code_day))
                self.nightIcon = "{}{}{}.png".format(host, path, str(WEATHER.weather_code_night))

            if self.is_loaded is False:
                self.animate_in()
                self.is_loaded = True

        except Exception as e:
            PIHOME_LOGGER.error(e)