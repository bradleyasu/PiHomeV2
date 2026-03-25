"""
weatherchips.py

Visually enhanced stat chip widgets for the weather overlay.
Each chip draws canvas-based visualizations behind its text labels.
"""

import math
from datetime import datetime, timedelta
from random import uniform, randint

from kivy.lang import Builder
from kivy.properties import (
    ColorProperty, StringProperty, NumericProperty, BooleanProperty,
)
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import (
    Color, RoundedRectangle, Rectangle, Ellipse, Line,
    InstructionGroup, PushMatrix, PopMatrix, Rotate,
)

# ── KV rules for all chips ──────────────────────────────────────────────────

Builder.load_string("""
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<WeatherChip>:
    orientation: 'vertical'
    padding: dp(10), dp(6), dp(10), dp(6)
    spacing: dp(2)
    canvas.before:
        Color:
            rgba: root.chip_bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
    Label:
        text: root.title_text
        color: root.text_color[0], root.text_color[1], root.text_color[2], 0.50
        font_size: '10sp'
        font_name: 'Nunito'
        halign: 'left'
        valign: 'middle'
        text_size: self.width, None
        size_hint_y: None
        height: dp(14)
    Label:
        text: root.value_text
        color: root.value_color
        font_size: '13sp'
        font_name: 'Nunito'
        bold: True
        halign: 'left'
        valign: 'middle'
        text_size: self.width, None
        size_hint_y: None
        height: dp(14)
    Widget:
        size_hint_y: 1

<HumidityChip>:
    orientation: 'vertical'
    padding: dp(10), dp(6), dp(10), dp(6)
    spacing: dp(2)
    canvas.before:
        Color:
            rgba: root.chip_bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
    Label:
        text: root.title_text
        color: root.text_color[0], root.text_color[1], root.text_color[2], 0.50
        font_size: '10sp'
        font_name: 'Nunito'
        halign: 'left'
        valign: 'middle'
        text_size: self.width, None
        size_hint_y: None
        height: dp(14)
    Label:
        text: root.value_text
        color: root.value_color
        font_size: '13sp'
        font_name: 'Nunito'
        bold: True
        halign: 'left'
        valign: 'middle'
        text_size: self.width, None
        size_hint_y: None
        height: dp(14)
    Label:
        text: root.sub_text
        color: root.text_color[0], root.text_color[1], root.text_color[2], 0.40
        font_size: '9sp'
        font_name: 'Nunito'
        halign: 'left'
        valign: 'middle'
        text_size: self.width, None
        size_hint_y: None
        height: dp(12)
    Widget:
        size_hint_y: 1
""")


# ── Base class ───────────────────────────────────────────────────────────────

class WeatherChip(BoxLayout):
    """Base for all stat chips. Provides title, value, and a canvas
    InstructionGroup for custom visualizations."""

    title_text = StringProperty("")
    value_text = StringProperty("--")
    value_color = ColorProperty([1, 1, 1, 1])
    chip_bg_color = ColorProperty([1, 1, 1, 0.07])
    text_color = ColorProperty([1, 1, 1, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._viz_group = InstructionGroup()
        self.canvas.before.add(self._viz_group)
        self.bind(pos=self._redraw, size=self._redraw)
        self._last_data = None

    def _redraw(self, *args):
        """Override in subclasses."""
        pass

    def update_data(self, weather):
        """Called by WeatherWidget.update() with the WEATHER singleton."""
        pass

    def on_config_update(self, config=None):
        """Called when theme changes."""
        pass


# ── 1. UV Index ──────────────────────────────────────────────────────────────

class UVChip(WeatherChip):

    _uv = NumericProperty(0)

    UV_COLORS = [
        (2,  [0.30, 0.80, 0.30, 1.0]),   # green
        (5,  [0.95, 0.85, 0.20, 1.0]),   # yellow
        (7,  [1.00, 0.60, 0.15, 1.0]),   # orange
        (10, [0.96, 0.30, 0.25, 1.0]),   # red
        (99, [0.58, 0.25, 0.85, 1.0]),   # purple
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_text = "UV Index"
        self.bind(_uv=self._redraw)

    @staticmethod
    def _uv_color(val):
        for threshold, color in UVChip.UV_COLORS:
            if val <= threshold:
                return color
        return UVChip.UV_COLORS[-1][1]

    def update_data(self, weather):
        uv = float(weather.uv_index)
        if uv == self._uv:
            return
        self._uv = uv
        self.value_text = str(int(uv))
        self.value_color = self._uv_color(uv)

    def _redraw(self, *args):
        self._viz_group.clear()
        if self.width == 0 or self.height == 0:
            return

        inset = dp(8)
        bar_y = self.y + dp(4)
        bar_h = dp(4)
        bar_w = self.width - inset * 2
        bar_x = self.x + inset

        # Dim track
        self._viz_group.add(Color(1, 1, 1, 0.08))
        self._viz_group.add(RoundedRectangle(
            pos=(bar_x, bar_y), size=(bar_w, bar_h), radius=[dp(2)]))

        # Filled portion
        fill_frac = min(self._uv / 11.0, 1.0)
        if fill_frac > 0:
            color = self._uv_color(self._uv)
            self._viz_group.add(Color(*color))
            self._viz_group.add(RoundedRectangle(
                pos=(bar_x, bar_y),
                size=(bar_w * fill_frac, bar_h),
                radius=[dp(2)]))


# ── 2. Wind ──────────────────────────────────────────────────────────────────

class WindChip(WeatherChip):

    _direction = NumericProperty(0)
    _display_dir = NumericProperty(0)
    _speed = NumericProperty(0)
    _gust = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_text = "Wind"
        self.bind(_display_dir=self._redraw)

    def update_data(self, weather):
        speed = weather.wind_speed
        gust = weather.wind_gust
        direction = weather.wind_direction

        if speed == self._speed and gust == self._gust and direction == self._direction:
            return

        self._speed = speed
        self._gust = gust

        # Format text
        if gust > speed + 5:
            self.value_text = "{} G{} mph".format(int(speed), int(gust))
        else:
            self.value_text = "{} mph".format(int(speed))

        # Animate compass arrow to new direction
        if direction != self._direction:
            self._direction = direction
            # Find shortest rotation path
            diff = (direction - self._display_dir + 180) % 360 - 180
            Animation(_display_dir=self._display_dir + diff, d=0.8, t='out_cubic').start(self)

    def _redraw(self, *args):
        self._viz_group.clear()
        if self.width == 0 or self.height == 0:
            return

        # Compass arrow in right portion of chip
        cx = self.right - dp(18)
        cy = self.center_y
        r = dp(10)
        angle_rad = math.radians(90 - self._display_dir)  # convert from meteorological

        # Arrow tip
        tip_x = cx + math.cos(angle_rad) * r
        tip_y = cy + math.sin(angle_rad) * r

        # Arrow base (two points forming a small triangle)
        base_angle1 = angle_rad + math.pi + 0.4
        base_angle2 = angle_rad + math.pi - 0.4
        b1x = cx + math.cos(base_angle1) * r * 0.5
        b1y = cy + math.sin(base_angle1) * r * 0.5
        b2x = cx + math.cos(base_angle2) * r * 0.5
        b2y = cy + math.sin(base_angle2) * r * 0.5

        # Compass circle (dim)
        self._viz_group.add(Color(1, 1, 1, 0.10))
        self._viz_group.add(Line(circle=(cx, cy, r), width=1))

        # Arrow
        self._viz_group.add(Color(self.text_color[0], self.text_color[1],
                                   self.text_color[2], 0.7))
        self._viz_group.add(Line(points=[b1x, b1y, tip_x, tip_y, b2x, b2y],
                                  width=1.3, close=True))


# ── 3. Precipitation (animated particles) ───────────────────────────────────

class PrecipParticle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'size', 'life', 'age', 'phase')

    def __init__(self, x, y, vx, vy, size, life):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.life = life
        self.age = 0.0
        self.phase = uniform(0, math.pi * 2)  # for snow drift


class PrecipChip(WeatherChip):

    _probability = NumericProperty(0)
    _intensity = NumericProperty(0)
    _is_snow = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_text = "Precip"
        self._particles = []
        self._clock_event = None
        self._spawn_timer = 0

    def update_data(self, weather):
        prob = weather.precip_propability
        intensity = weather.precip_intensity
        is_snow = weather.temperature <= 32

        self._probability = prob
        self._intensity = intensity
        self._is_snow = is_snow
        self.value_text = "{}%".format(int(prob))

    def start_particles(self):
        if self._clock_event is None:
            self._clock_event = Clock.schedule_interval(self._tick, 1 / 20.0)

    def stop_particles(self):
        if self._clock_event is not None:
            self._clock_event.cancel()
            self._clock_event = None
        self._particles.clear()
        self._viz_group.clear()

    def _tick(self, dt):
        if self._intensity <= 0 and self._probability <= 10:
            if self._particles:
                self._particles.clear()
                self._viz_group.clear()
            return

        # Spawn new particles
        spawn_rate = max(0.08, 0.5 - self._intensity * 0.3)
        self._spawn_timer += dt
        while self._spawn_timer >= spawn_rate and len(self._particles) < 12:
            self._spawn_timer -= spawn_rate
            self._spawn_particle()

        # Update existing particles
        dead = []
        for p in self._particles:
            p.age += dt
            if self._is_snow:
                p.x += math.sin(p.age * 2.0 + p.phase) * dp(8) * dt
                p.y += p.vy * dt
            else:
                p.x += p.vx * dt
                p.y += p.vy * dt
            if p.age >= p.life or p.y < self.y:
                dead.append(p)

        for p in dead:
            self._particles.remove(p)

        self._redraw_particles()

    def _spawn_particle(self):
        x = uniform(self.x + dp(4), self.right - dp(4))
        y = self.top - dp(2)
        if self._is_snow:
            vy = -uniform(dp(15), dp(25))
            vx = 0
            size = uniform(2.0, 3.5)
            life = uniform(1.5, 2.5)
        else:
            vy = -uniform(dp(40), dp(70))
            vx = uniform(-dp(3), dp(3))
            size = uniform(1.5, 2.5)
            life = uniform(0.6, 1.2)
        self._particles.append(PrecipParticle(x, y, vx, vy, size, life))

    def _redraw_particles(self):
        self._viz_group.clear()
        for p in self._particles:
            opacity = max(0, 1.0 - (p.age / p.life))
            if self._is_snow:
                self._viz_group.add(Color(0.9, 0.93, 1.0, opacity * 0.7))
            else:
                self._viz_group.add(Color(0.4, 0.6, 1.0, opacity * 0.6))
            self._viz_group.add(Ellipse(
                pos=(p.x - p.size / 2, p.y - p.size / 2),
                size=(p.size, p.size)))


# ── 4. Humidity + Dew Point ──────────────────────────────────────────────────

class HumidityChip(BoxLayout):
    """Humidity chip with fill bar and dew point sub-text."""

    title_text = StringProperty("Humidity")
    value_text = StringProperty("--")
    value_color = ColorProperty([1, 1, 1, 1])
    sub_text = StringProperty("")
    chip_bg_color = ColorProperty([1, 1, 1, 0.07])
    text_color = ColorProperty([1, 1, 1, 1])

    _humidity = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._viz_group = InstructionGroup()
        self.canvas.before.add(self._viz_group)
        self.bind(pos=self._redraw, size=self._redraw, _humidity=self._redraw)
        self._last_data = None

    def update_data(self, weather):
        h = weather.humidity
        dp_val = weather.dew_point
        if h == self._humidity and self.sub_text:
            return
        self._humidity = h
        self.value_text = "{}%".format(int(h))
        self.sub_text = "DP {}\u00B0".format(int(dp_val))

    def _redraw(self, *args):
        self._viz_group.clear()
        if self.width == 0 or self.height == 0 or self._humidity == 0:
            return

        # Vertical fill bar on right side
        bar_w = dp(6)
        bar_h = self.height - dp(12)
        bar_x = self.right - dp(12)
        bar_y = self.y + dp(6)

        # Track
        self._viz_group.add(Color(1, 1, 1, 0.08))
        self._viz_group.add(RoundedRectangle(
            pos=(bar_x, bar_y), size=(bar_w, bar_h), radius=[dp(3)]))

        # Fill
        fill_h = (self._humidity / 100.0) * bar_h
        # Color: light blue (low) → deep blue (high)
        frac = self._humidity / 100.0
        r = 0.35 * (1 - frac) + 0.20 * frac
        g = 0.65 * (1 - frac) + 0.40 * frac
        b = 0.95 * (1 - frac) + 1.00 * frac
        self._viz_group.add(Color(r, g, b, 0.7))
        self._viz_group.add(RoundedRectangle(
            pos=(bar_x, bar_y), size=(bar_w, fill_h), radius=[dp(3)]))

    def on_config_update(self, config=None):
        pass


# ── 5. Cloud Cover ───────────────────────────────────────────────────────────

class CloudChip(WeatherChip):

    _cover = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_text = "Clouds"
        self.bind(_cover=self._redraw)

    def update_data(self, weather):
        cover = weather.cloud_cover
        if cover == self._cover:
            return
        self._cover = cover
        self.value_text = "{}%".format(int(cover))

    def _redraw(self, *args):
        self._viz_group.clear()
        if self.width == 0 or self.height == 0:
            return

        cover = self._cover
        opacity = 0.12 + (cover / 100.0) * 0.50
        dark = self.chip_bg_color[0] < 0.5
        cloud_color = [1, 1, 1] if dark else [0.5, 0.5, 0.55]

        cx = self.right - dp(22)
        cy = self.center_y - dp(2)
        s = dp(10)

        if cover <= 0:
            return

        # Always draw at least one cloud
        self._draw_cloud(cx, cy, s, cloud_color, opacity)

        if cover > 25:
            self._draw_cloud(cx - s * 0.7, cy + s * 0.2, s * 0.75, cloud_color, opacity * 0.8)

        if cover > 65:
            self._draw_cloud(cx + s * 0.3, cy - s * 0.35, s * 0.65, cloud_color, opacity * 0.7)

    def _draw_cloud(self, cx, cy, s, color, opacity):
        self._viz_group.add(Color(color[0], color[1], color[2], opacity))
        # Three overlapping ellipses form a cloud
        self._viz_group.add(Ellipse(
            pos=(cx - s * 0.55, cy - s * 0.15), size=(s * 0.55, s * 0.40)))
        self._viz_group.add(Ellipse(
            pos=(cx - s * 0.15, cy + s * 0.05), size=(s * 0.60, s * 0.45)))
        self._viz_group.add(Ellipse(
            pos=(cx + s * 0.2, cy - s * 0.10), size=(s * 0.50, s * 0.35)))


# ── 6. Sunset / Moon Phase ──────────────────────────────────────────────────

class SunMoonChip(WeatherChip):

    _is_day = BooleanProperty(True)
    _moon_phase = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_text = "Sunset"
        self.bind(_is_day=self._redraw, _moon_phase=self._redraw)

    def update_data(self, weather):
        is_day = weather.is_currently_day()
        self._is_day = is_day
        self._moon_phase = int(weather.moon_phase)

        if is_day:
            self.title_text = "Sunset"
            self.value_text = self._time_until(weather.sunset_time)
            self.value_color = [1.0, 0.75, 0.30, 1.0]
        else:
            phase_idx = min(int(weather.moon_phase), len(weather.moon_phase_lookup) - 1)
            self.title_text = weather.moon_phase_lookup[phase_idx]
            self.value_text = self._time_until(weather.sunrise_time)
            self.value_color = [0.75, 0.80, 0.90, 1.0]

    @staticmethod
    def _time_until(time_str):
        """Compute human-readable time remaining until an ISO 8601 UTC time."""
        try:
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            target = datetime.strptime(time_str, fmt)
            now = datetime.utcnow()
            delta = target - now
            if delta.total_seconds() < 0:
                return "--"
            hours = int(delta.total_seconds() // 3600)
            mins = int((delta.total_seconds() % 3600) // 60)
            if hours > 0:
                return "{}h {}m".format(hours, mins)
            return "{}m".format(mins)
        except Exception:
            return "--"

    def _redraw(self, *args):
        self._viz_group.clear()
        if self.width == 0 or self.height == 0:
            return

        cx = self.right - dp(18)
        cy = self.center_y
        r = dp(8)

        if self._is_day:
            self._draw_sun(cx, cy, r)
        else:
            self._draw_moon(cx, cy, r)

    def _draw_sun(self, cx, cy, r):
        # Warm sun circle
        self._viz_group.add(Color(1.0, 0.80, 0.25, 0.6))
        self._viz_group.add(Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2)))

        # Subtle glow
        self._viz_group.add(Color(1.0, 0.80, 0.25, 0.15))
        gr = r * 1.5
        self._viz_group.add(Ellipse(pos=(cx - gr, cy - gr), size=(gr * 2, gr * 2)))

        # Small rays
        self._viz_group.add(Color(1.0, 0.80, 0.25, 0.35))
        for i in range(8):
            angle = math.radians(i * 45)
            x1 = cx + math.cos(angle) * (r + dp(2))
            y1 = cy + math.sin(angle) * (r + dp(2))
            x2 = cx + math.cos(angle) * (r + dp(5))
            y2 = cy + math.sin(angle) * (r + dp(5))
            self._viz_group.add(Line(points=[x1, y1, x2, y2], width=1))

    def _draw_moon(self, cx, cy, r):
        # Moon phase: 0=New, 1=WaxCrescent, 2=FirstQ, 3=WaxGibbous,
        #             4=Full, 5=WanGibbous, 6=ThirdQ, 7=WanCrescent
        phase = self._moon_phase

        # Bright moon circle
        brightness = 0.75
        self._viz_group.add(Color(0.85, 0.88, 0.95, brightness))
        self._viz_group.add(Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2)))

        if phase == 4:
            # Full moon — no overlay needed
            return
        if phase == 0:
            # New moon — cover entirely
            bg = self._get_opaque_bg()
            self._viz_group.add(Color(*bg))
            self._viz_group.add(Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2)))
            return

        # Crescent/quarter/gibbous: overlay circle offset to create shadow
        # Phases 1-3: waxing (shadow on left, moving right)
        # Phases 5-7: waning (shadow on right, moving left)
        bg = self._get_opaque_bg()
        self._viz_group.add(Color(*bg))

        if phase <= 3:
            # Waxing: shadow shrinks from left
            # phase 1: large shadow offset left, phase 3: small offset
            frac = (4 - phase) / 4.0  # 1->0.75, 2->0.5, 3->0.25
            offset = -r * 2 * frac
        else:
            # Waning: shadow grows from right
            frac = (phase - 4) / 4.0  # 5->0.25, 6->0.5, 7->0.75
            offset = r * 2 * frac

        overlay_r = r * 1.1
        self._viz_group.add(Ellipse(
            pos=(cx - overlay_r + offset, cy - overlay_r),
            size=(overlay_r * 2, overlay_r * 2)))

    def _get_opaque_bg(self):
        """Compute an opaque color approximation of chip_bg over a dark card."""
        bg = self.chip_bg_color
        # Assume dark card base of ~(0.08, 0.10, 0.14)
        card = [0.08, 0.10, 0.14]
        a = bg[3]
        r = card[0] * (1 - a) + bg[0] * a
        g = card[1] * (1 - a) + bg[1] * a
        b = card[2] * (1 - a) + bg[2] * a
        return [r, g, b, 1.0]
