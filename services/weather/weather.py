from datetime import datetime
import os
import time
# import pytz
import requests
from threading import Thread
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from networking.poller import POLLER
from services.weather.insight import Insight
from util.configuration import CONFIG
from util.helpers import get_app, toast
from util.phlog import PIHOME_LOGGER

class Weather:
    """
    Weather interface with tomorrow.io api to fetch current weather information
    based on latitude and longitude location 
    """
    api_url = "https://api.tomorrow.io/v4/timelines?location={},{}&fields=weatherCodeFullDay,rainAccumulation,cloudCover,snowAccumulation,temperature,temperatureApparent,dewPoint,moonPhase,humidity,windSpeed,windGust,uvIndex,weatherCode,weatherCodeDay,weatherCodeNight,visibility,precipitationProbability,precipitationIntensity,windDirection,sunriseTime,sunsetTime&timesteps=current,1h,1d&units=imperial&apikey={}"

    insight_api_url = "https://api.tomorrow.io/v4/events?insights=thunderstorms&insights=air&insights=wind&insights=floods&insights=winter&insights=tornado&insights=temperature&buffer=1&location={},{}&apikey={}"

    latitude = 0
    longitude = 0 
    api_key = ""

    data_avail = False
    interval = 60 * 10 # 60 seconds time 30 for 10 minute update interval 

    weather_code = 0 # Current weather Code
    weather_code_day = 0 # Weather for today, sunrise to sunset
    weather_code_night = 0 # Weather code during the night
    snow_accumulation = 0
    rain_accumulation = 0
    temperature = 0
    feels_like = 0
    humidity = 0
    wind_speed = 0
    wind_direction = 0
    wind_gust = 0
    sunrise_time = 0
    sunset_time = 0
    precip_propability = 0
    precip_intensity = 0
    cloud_cover = 0
    moon_phase = 0
    uv_index = 0
    dew_point = 0

    epa_air_quality = 0 # Lower is better

    moon_phase_lookup = [
        "New", "Waxing Crescent", "First Quarter", "Waxing Gibbous", "Full", "Waning Gibbous", "Third Quarter", "Waning Crescent"
    ]

    epa_air_lookup = ["Good", "Moderate", "Unhealthy for Sensitive Groups", "Unhealthy", "Very Unhealthy", "Hazardous"]

    future = []
    future_daily = []

    insights = []

    def __init__(self, **kwargs):
        super(Weather, self).__init__(**kwargs)
        self.enabled = CONFIG.get_int("weather", "enabled", 0)
        self.api_key = CONFIG.get("weather", "api_key", '')
        self.latitude = CONFIG.get("weather", "latitude", '0')
        self.longitude = CONFIG.get("weather", "longitude", '0')
        if self.enabled == 1:
            if self.api_key != "":
                self.register_weather_api_call(self.api_url.format(self.latitude, self.longitude, self.api_key), self.interval, self.update_weather)
                self.register_weather_api_call(self.insight_api_url.format(self.latitude, self.longitude, self.api_key), self.interval, self.update_insights)
            else:
                PIHOME_LOGGER.warn("[ WEATHER ] Weather is enabled but no API key is set.  Weather features are disabled.")
                Clock.schedule_once(lambda _: toast("Weather API key is not set, please configure in settings", "warn", 10), 15)
        else: 
            PIHOME_LOGGER.info("[ WEATHER ] Weather is disabled.")
                
    def register_weather_api_call(self, url, interval, on_resp):
        POLLER.register_api(url, interval, on_resp);

    def update_weather(self, weather_data):
        data = weather_data["data"]["timelines"]
        for value in data:
            if value["timestep"] == '1d':
                self.proc_forcast(value)
                self.future_daily = value["intervals"]
            if value["timestep"] == '1h':
                self.future = value["intervals"]
            if value["timestep"] == 'current':
                self.proc_current(value)

    def update_insights(self, insight_data):
        self.insights = Insight.from_response(insight_data)

    def proc_forcast(self, data):
        #self.future = data["intervals"]
        data = data["intervals"][0]["values"]
        self.weather_code_day = data["weatherCodeDay"]
        self.weather_code_night = data["weatherCodeNight"]

    
    def proc_current(self, data):
        data = data["intervals"][0]["values"]
        self.data_avail = True
        self.uv_index = data["uvIndex"];
        self.precip_propability = data["precipitationProbability"]
        self.precip_intensity = data["precipitationIntensity"]
        self.temperature = data["temperature"]
        self.wind_speed = data["windSpeed"]
        self.wind_direction = data["windDirection"]
        self.humidity = data["humidity"]
        self.weather_code = data["weatherCode"]
        self.sunrise_time = data["sunriseTime"]
        self.sunset_time = data["sunsetTime"]
        self.feels_like = data["temperatureApparent"]
        self.rain_accumulation = data["rainAccumulation"]
        self.snow_accumulation = data["snowAccumulation"]
        self.wind_gust = data["windGust"]
        self.moon_phase = data["moonPhase"]
        self.dew_point = data["dewPoint"]
        self.cloud_cover = data.get("cloudCover", 0)

    def is_currently_day(self, dt=None):
        """
        Compare the given UTC datetime (or now if omitted) against the stored
        sunrise/sunset strings to determine whether it is daytime.
        Sunrise/sunset come from tomorrow.io as ISO-8601 UTC strings,
        e.g. "2022-08-02T10:24:00Z".
        """
        try:
            if dt is None:
                dt = datetime.utcnow()
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            sunrise = datetime.strptime(self.sunrise_time, fmt)
            sunset  = datetime.strptime(self.sunset_time,  fmt)
            return sunrise <= dt <= sunset
        except Exception:
            return True


WEATHER = Weather()