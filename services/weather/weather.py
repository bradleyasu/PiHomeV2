from datetime import datetime
import os
import time
# import pytz
import requests
from threading import Thread
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from util.helpers import get_app, get_config, get_poller, info, toast, warn

class Weather:
    """
    Weather interface with tomorrow.io api to fetch current weather information
    based on latitude and longitude location 
    """
    api_url = "https://api.tomorrow.io/v4/timelines?location={},{}&fields=temperature,temperatureApparent,humidity,windSpeed,uvIndex,weatherCode,weatherCodeDay,weatherCodeNight,visibility,precipitationProbability,precipitationIntensity,windSpeed,windDirection,sunriseTime,sunsetTime&timesteps=current,1d&units=imperial&apikey={}"
    latitude = 0
    longitude = 0 
    api_key = ""

    data_avail = False
    interval = 60 * 30 # 60 seconds time 30 for 30 minute update interval 

    weather_code = 0 # Current weather Code
    weather_code_day = 0 # Weather for today, sunrise to sunset
    weather_code_night = 0 # Weather code during the night
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

    epa_air_quality = 0 # Lower is better

    moon_phase_lookup = [
        "New", "Waxing Crescent", "First Quarter", "Waxing Gibbous", "Full", "Waning Gibbous", "Third Quarter", "Waning Crescent"
    ]

    epa_air_lookup = ["Good", "Moderate", "Unhealthy for Sensitive Groups", "Unhealthy", "Very Unhealthy", "Hazardous"]

    future = []

    def __init__(self, **kwargs):
        super(Weather, self).__init__(**kwargs)
        self.enabled = get_config().get_int("weather", "enabled", 0)
        self.api_key = get_config().get("weather", "api_key", '')
        self.latitude = get_config().get("weather", "latitude", '0')
        self.longitude = get_config().get("weather", "longitude", '0')
        if self.enabled == 1:
            if self.api_key != "":
                self.register_weather_api_call(self.api_url.format(self.latitude, self.longitude, self.api_key), self.interval, self.update_weather)
            else:
                warn("[ WEATHER ] Weather is enabled but no API key is set.  Weather features are disabled.")
                Clock.schedule_once(lambda _: toast("Weather API key is not set, please configure in settings", "warn", 10), 15)
        else: 
            info("[ WEATHER ] Weather is disabled.")
                
    def register_weather_api_call(self, url, interval, on_resp):
        get_poller().register_api(url, interval, on_resp);

    def update_weather(self, weather_data):
        data = weather_data["data"]["timelines"]
        for value in data:
            if value["timestep"] == '1d':
                self.proc_forcast(value)
            if value["timestep"] == 'current':
                self.proc_current(value)



    def proc_forcast(self, data):
        self.future = data["intervals"]
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

    def is_currently_day(self):
        """
        Compare current time with sunrise/sunset times to determine
        if it is currently daylight outside
        """
        # current_time = datetime.now()
        # Time format = 2022-08-01T10:23:00Z
        # start_time = datetime.strptime(self.sunrise_time, "%Y-%m-%dT%H:%M:%SZ")
        # end_time = datetime.strptime(self.sunset_time, "%Y-%m-%dT%H:%M:%SZ")

        # return start_time < current_time < end_time
        return True