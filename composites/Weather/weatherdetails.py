from datetime import datetime, timezone, timedelta
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ColorProperty, NumericProperty, StringProperty, DictProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Line, Mesh, RoundedRectangle, InstructionGroup
from kivy.graphics.texture import Texture
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

    # ── Temperature trend ──
    temp_value = NumericProperty(0)
    next_temp_value = NumericProperty(0)

    # ── UV trend ──
    uv_value = NumericProperty(0)
    next_uv_value = NumericProperty(0)

    # ── Wind trend ──
    wind_value = NumericProperty(0)
    next_wind_value = NumericProperty(0)

    # ── Active trend metric ──
    trend_metric = StringProperty("temp")  # "temp", "uv", "wind"
    metric_label = StringProperty("--")

    # ── Precipitation accumulation ──
    rain_accum = NumericProperty(0)
    snow_accum = NumericProperty(0)

    # Shared gradient texture (1x2 px: opaque white at top, transparent at bottom)
    _gradient_tex = None

    @classmethod
    def _get_gradient_texture(cls):
        if cls._gradient_tex is None:
            tex = Texture.create(size=(1, 2), colorfmt='rgba')
            buf = bytes([255, 255, 255, 70,
                         255, 255, 255, 0])
            tex.blit_buffer(buf, colorfmt='rgba', bufferfmt='ubyte')
            cls._gradient_tex = tex
        return cls._gradient_tex

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
        self._parse_event = Clock.schedule_interval(lambda _: self.parseDetails(), 1)

        # Temperature trend line + gradient
        self._trend_group = InstructionGroup()
        self.canvas.before.add(self._trend_group)
        # Precipitation bar (drawn after trend so it layers on top)
        self._precip_group = InstructionGroup()
        self.canvas.before.add(self._precip_group)
        self.bind(pos=self._draw_trend, size=self._draw_trend,
                  temp_value=self._draw_trend, next_temp_value=self._draw_trend,
                  uv_value=self._draw_trend, next_uv_value=self._draw_trend,
                  wind_value=self._draw_trend, next_wind_value=self._draw_trend,
                  trend_metric=self._draw_trend,
                  rain_accum=self._draw_trend, snow_accum=self._draw_trend)

    def cleanup(self):
        """Cancel the periodic parse clock. Call when removing this widget."""
        if self._parse_event:
            self._parse_event.cancel()
            self._parse_event = None

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
                    "snowAccumulation": 0,
                    "rainAccumulation": 0,
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
        raw_temp = details["values"]["temperature"]
        self.temp_value = raw_temp
        self.temp = "{}\u00B0F".format(round(raw_temp))
        self.uv_value = details["values"].get("uvIndex", 0) or 0
        self.wind_value = details["values"].get("windSpeed", 0) or 0
        self.precip = "{}%".format(round(details["values"]["precipitationProbability"]))
        self.rain_accum = details["values"].get("rainAccumulation", 0) or 0
        self.snow_accum = details["values"].get("snowAccumulation", 0) or 0
        self._update_metric_label()

        conf = get_app().web_conf
        if conf != None:
            host = conf["host"]
            path = conf["weather_icons"]
            if self.is_daily:
                # Use weatherCodeFullDay with daytime icon variant for daily cards
                code = details["values"].get("weatherCodeFullDay", details["values"]["weatherCode"])
                self.icon = "{}{}{}0.png".format(host, path, str(code))
                self.icon_fallback = "{}{}{}0.png".format(host, path, str(code))
            else:
                day_code = 0 if WEATHER.is_currently_day(slot_dt) else 1
                self.icon = "{}{}{}{}.png".format(host, path, str(details["values"]["weatherCode"]), day_code)
                self.icon_fallback = "{}{}{}{}.png".format(host, path, str(details["values"]["weatherCode"]), 0)

    def _update_metric_label(self):
        """Update the display label based on the active trend metric."""
        if self.trend_metric == "uv":
            self.metric_label = "UV {}".format(round(self.uv_value))
        elif self.trend_metric == "wind":
            self.metric_label = "{} mph".format(round(self.wind_value))
        else:
            self.metric_label = self.temp

    def on_trend_metric(self, instance, value):
        self._update_metric_label()

    # ── Trend rendering ──

    @staticmethod
    def _temp_to_color(temp_f):
        """Map Fahrenheit temperature to an RGB color list."""
        t = max(0.0, min(110.0, temp_f))
        norm = t / 110.0
        if norm < 0.29:       # 0–32°F: cold blue
            return [0.25, 0.50, 1.0]
        elif norm < 0.50:     # 32–55°F: blue → cyan
            f = (norm - 0.29) / 0.21
            return [0.25 * (1 - f),
                    0.50 * (1 - f) + 0.85 * f,
                    1.0]
        elif norm < 0.68:     # 55–75°F: cyan → warm yellow
            f = (norm - 0.50) / 0.18
            return [f,
                    0.85 * (1 - f) + 0.90 * f,
                    1.0 * (1 - f) + 0.25 * f]
        elif norm < 0.82:     # 75–90°F: yellow → orange
            f = (norm - 0.68) / 0.14
            return [1.0,
                    0.90 * (1 - f) + 0.50 * f,
                    0.25 * (1 - f) + 0.10 * f]
        else:                 # 90–110°F: orange → red
            f = min(1.0, (norm - 0.82) / 0.18)
            return [1.0,
                    0.50 * (1 - f) + 0.15 * f,
                    0.10]

    @staticmethod
    def _temp_to_y(temp, y_min, y_max):
        """Map temperature (°F) to a y coordinate within a range."""
        t = max(0.0, min(110.0, temp))
        return y_min + (t / 110.0) * (y_max - y_min)

    @staticmethod
    def _uv_to_color(uv):
        """Map UV index (0–11+) to an RGB color list."""
        u = max(0.0, min(11.0, uv))
        norm = u / 11.0
        if norm < 0.27:       # 0–3: green (low)
            return [0.30, 0.75, 0.30]
        elif norm < 0.55:     # 3–6: yellow (moderate)
            f = (norm - 0.27) / 0.28
            return [0.30 + 0.70 * f,
                    0.75 + 0.15 * f,
                    0.30 * (1 - f)]
        elif norm < 0.73:     # 6–8: orange (high)
            f = (norm - 0.55) / 0.18
            return [1.0,
                    0.90 * (1 - f) + 0.50 * f,
                    0.10 * f]
        else:                 # 8–11: red/violet (very high)
            f = min(1.0, (norm - 0.73) / 0.27)
            return [1.0 * (1 - f) + 0.70 * f,
                    0.50 * (1 - f) + 0.15 * f,
                    0.10 + 0.55 * f]

    @staticmethod
    def _uv_to_y(uv, y_min, y_max):
        """Map UV index (0–11) to a y coordinate within a range."""
        u = max(0.0, min(11.0, uv))
        return y_min + (u / 11.0) * (y_max - y_min)

    @staticmethod
    def _wind_to_color(speed):
        """Map wind speed (mph, 0–60+) to an RGB color list."""
        s = max(0.0, min(60.0, speed))
        norm = s / 60.0
        if norm < 0.17:       # 0–10 mph: light teal (calm)
            return [0.45, 0.80, 0.85]
        elif norm < 0.42:     # 10–25 mph: teal → blue
            f = (norm - 0.17) / 0.25
            return [0.45 * (1 - f) + 0.25 * f,
                    0.80 * (1 - f) + 0.55 * f,
                    0.85 + 0.15 * f]
        elif norm < 0.67:     # 25–40 mph: blue → yellow
            f = (norm - 0.42) / 0.25
            return [0.25 + 0.75 * f,
                    0.55 * (1 - f) + 0.85 * f,
                    1.0 * (1 - f) + 0.20 * f]
        else:                 # 40–60 mph: yellow → red (severe)
            f = min(1.0, (norm - 0.67) / 0.33)
            return [1.0,
                    0.85 * (1 - f) + 0.20 * f,
                    0.20 * (1 - f)]

    @staticmethod
    def _wind_to_y(speed, y_min, y_max):
        """Map wind speed (mph, 0–60) to a y coordinate within a range."""
        s = max(0.0, min(60.0, speed))
        return y_min + (s / 60.0) * (y_max - y_min)

    def _draw_trend(self, *args):
        """Redraw the trend line and gradient fill for the active metric."""
        self._trend_group.clear()

        metric = self.trend_metric
        if metric == "uv":
            cur_val = self.uv_value
            nxt_val = self.next_uv_value if self.next_uv_value != 0 else cur_val
            to_y = self._uv_to_y
            to_color = self._uv_to_color
        elif metric == "wind":
            cur_val = self.wind_value
            nxt_val = self.next_wind_value if self.next_wind_value != 0 else cur_val
            to_y = self._wind_to_y
            to_color = self._wind_to_color
        else:
            cur_val = self.temp_value
            nxt_val = self.next_temp_value if self.next_temp_value != 0 else cur_val
            to_y = self._temp_to_y
            to_color = self._temp_to_color

        if cur_val == 0 and metric == "temp":
            return

        # Vertical range for the trend (leave room for label at top, text at bottom)
        y_min = self.y + dp(8)
        y_max = self.y + self.height - dp(22)

        y_start = to_y(cur_val, y_min, y_max)
        y_end = to_y(nxt_val, y_min, y_max)

        left = self.x
        right = self.x + self.width
        bottom = self.y

        avg_val = (cur_val + nxt_val) / 2.0
        color = to_color(avg_val)

        # Gradient fill: trapezoid from line down to card bottom
        # Opaque at bottom, fading to transparent at the trend line
        self._trend_group.add(Color(color[0], color[1], color[2], 1.0))
        vertices = [
            left,  y_start, 0.0, 0.0,   # top-left  (at line) — transparent
            right, y_end,   1.0, 0.0,   # top-right (at line) — transparent
            right, bottom,  1.0, 1.0,   # bottom-right — opaque
            left,  bottom,  0.0, 1.0,   # bottom-left — opaque
        ]
        indices = [0, 1, 2, 0, 2, 3]
        self._trend_group.add(
            Mesh(vertices=vertices, indices=indices,
                 mode='triangles', texture=self._get_gradient_texture())
        )

        # Trend line on top
        self._trend_group.add(Color(color[0], color[1], color[2], 0.9))
        self._trend_group.add(Line(points=[left, y_start, right, y_end], width=1.2))

        # ── Precipitation accumulation bars ──
        self._precip_group.clear()
        rain = self.rain_accum
        snow = self.snow_accum
        if rain <= 0 and snow <= 0:
            return

        # Map accumulation to bar height
        # Daily totals can be much larger than hourly
        max_accum = 6.0 if self.is_daily else 2.0
        bar_max_h = dp(28)
        bar_inset = dp(4)
        bar_left = left + bar_inset
        bar_width = (right - left) - bar_inset * 2
        bar_bottom = bottom + dp(2)
        bar_radius = dp(3)

        # Snow bar (stacks on top of rain)
        y_cursor = bar_bottom
        if rain > 0:
            rain_h = min(rain / max_accum, 1.0) * bar_max_h
            self._precip_group.add(Color(0.30, 0.55, 0.95, 0.55))
            self._precip_group.add(
                RoundedRectangle(
                    pos=(bar_left, y_cursor),
                    size=(bar_width, rain_h),
                    radius=[bar_radius]
                )
            )
            y_cursor += rain_h

        if snow > 0:
            snow_h = min(snow / max_accum, 1.0) * bar_max_h
            self._precip_group.add(Color(0.85, 0.90, 1.0, 0.55))
            self._precip_group.add(
                RoundedRectangle(
                    pos=(bar_left, y_cursor),
                    size=(bar_width, snow_h),
                    radius=[bar_radius]
                )
            )