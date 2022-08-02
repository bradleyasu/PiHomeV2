from composites.Weather.weatherdetails import WeatherDetails
from kivy.lang import Builder
from kivy.properties import Property, ColorProperty, StringProperty, NumericProperty, DictProperty, ListProperty, ObjectProperty, ReferenceListProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.clock import Clock
from theme.theme import Theme

from util.helpers import get_app, weather

Builder.load_file("./composites/Weather/weatherwidget.kv")

class WeatherWidget(Widget):
    theme = Theme()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY))

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

        if(weather().enabled):
            Clock.schedule_interval(lambda _: self.update(), 10)

   
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
        self.temp = str(round(weather().temperature))
        self.uvIndex = str(weather().uv_index)
        self.windSpeed = "{} MPH".format(weather().wind_speed)
        self.precipPercent = "{}%".format(weather().precip_propability)
        self.humidity = "{}%".format(weather().humidity)
        self.airQuality = weather().epa_air_lookup[weather().epa_air_quality]
        self.sunrise = "{}".format(weather().sunrise_time)
        self.sunset = "{}".format(weather().sunset_time)
        self.feelsLike = "{}".format(weather().feels_like)
        self.future = weather().future
        self.day = weather().future[1]


        conf = get_app().web_conf
        if conf != None:
            host = conf["host"]
            path = conf["weather_icons"]
            day_code = 0
            if weather().is_currently_day() == False:
                day_code = 1
            self.icon = "{}{}{}{}.png".format(host, path, str(weather().weather_code), str(day_code))
            self.dayIcon = "{}{}{}.png".format(host, path, str(weather().weather_code_day))
            self.nightIcon = "{}{}{}.png".format(host, path, str(weather().weather_code_night))
        
        if self.is_loaded == False:
            self.animate_in()
            self.is_loaded = True