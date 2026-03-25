from datetime import datetime, timezone

from composites.Weather.weatherdetails import WeatherDetails
from kivy.lang import Builder
from kivy.properties import Property, BooleanProperty, ColorProperty, StringProperty, NumericProperty, DictProperty, ListProperty, ObjectProperty, ReferenceListProperty
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.carousel import Carousel
from kivy.uix.floatlayout import FloatLayout
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse, Line
from services.weather.weather import WEATHER
from services.weather.insight import Insight, Severity
from theme.theme import Theme
from util.configuration import CONFIG
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
    icon_large = StringProperty("")
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
    overlay_size = ListProperty([100, 100])

    pill_stat = StringProperty("")
    pill_stat_color = ColorProperty([1.0, 1.0, 1.0, 1.0])
    pill_icon = StringProperty("")
    icon_fallback = StringProperty("")  # always the daytime variant; used when night icon is missing
    icon_fallback_large = StringProperty("")  # always the daytime variant; used when night icon is missing

    # Theme-aware surface colors — set at runtime from Theme().mode
    card_color         = ColorProperty([0.08, 0.10, 0.14, 1.0])
    card_border_color  = ColorProperty([1.0, 1.0, 1.0, 0.10])
    chip_bg_color      = ColorProperty([1.0, 1.0, 1.0, 0.07])
    divider_color      = ColorProperty([1.0, 1.0, 1.0, 0.12])
    pill_bg_color      = ColorProperty([0.08, 0.10, 0.14, 1.0])
    pill_border_color  = ColorProperty([1.0, 1.0, 1.0, 0.10])
    pill_divider_color = ColorProperty([1.0, 1.0, 1.0, 0.22])

    is_loaded = False
    show_hourly = BooleanProperty(True)
    future_daily = ListProperty([])

    y_offset = NumericProperty(50)

    # ── Forecast scroll state ──
    _hourly_count = 0   # track widget count to avoid unnecessary rebuilds
    _daily_count = 0

    # ── Alert carousel state ──
    alert_count = NumericProperty(0)
    alert_opacity = NumericProperty(0)

    def _apply_theme_colors(self):
        dark = Theme().mode == 1
        # Refresh text_color so light/dark switch is respected at runtime
        t = Theme()
        self.text_color = t.get_color(t.TEXT_PRIMARY)
        if dark:
            self.card_color         = [0.08, 0.10, 0.14, 1.0]
            self.card_border_color  = [1.0, 1.0, 1.0, 0.10]
            self.chip_bg_color      = [1.0, 1.0, 1.0, 0.07]
            self.divider_color      = [1.0, 1.0, 1.0, 0.12]
            self.pill_bg_color      = [0.08, 0.10, 0.14, 1.0]
            self.pill_border_color  = [1.0, 1.0, 1.0, 0.10]
            self.pill_divider_color = [1.0, 1.0, 1.0, 0.22]
        else:
            self.card_color         = [0.98, 0.98, 0.99, 1.0]
            self.card_border_color  = [0.0,  0.0,  0.0,  0.10]
            self.chip_bg_color      = [0.0,  0.0,  0.0,  0.05]
            self.divider_color      = [0.0,  0.0,  0.0,  0.10]
            self.pill_bg_color      = [0.98, 0.98, 0.99, 1.0]
            self.pill_border_color  = [0.0,  0.0,  0.0,  0.12]
            self.pill_divider_color = [0.0,  0.0,  0.0,  0.20]
        # Default the pill stat to text_color so it's always readable before
        # the first weather update populates a real value
        self.pill_stat_color = list(self.text_color)

    def __init__(self, size=(dp(100), dp(50)), pos=(dp(0), dp(0)), delay = 0, **kwargs):
        super(WeatherWidget, self).__init__(**kwargs)
        self.size = size
        self.pos = pos
        self.overlay_size = [Window.width - dp(40), Window.height - dp(80)]
        self._apply_theme_colors()
        self._clock_event = None
        self._last_alert_keys = []

        if CONFIG.get_int("weather", "enabled", 0) == 1:
            self._clock_event = Clock.schedule_interval(lambda _: self.update(), 1)
            PIHOME_LOGGER.info("Weather is enabled.  Weather update thread will be running.")
        else:
            self.opacity = 0
            PIHOME_LOGGER.warn("Weather is not enabled.  Weather update thread will not be running.")

    def on_touch_down(self, touch):
        if self.is_loaded == False:
            return False
        # Only respond to touches that land on the visible pill, not the full-width widget
        pill_x = self.right - dp(178)
        pill_y = self.y + dp(self.y_offset)
        if (pill_x <= touch.x <= pill_x + dp(178) and
                pill_y <= touch.y <= pill_y + dp(44)):
            if self.overlay_active == True:
                self.overlay_animate(opacity = 0, offset = 10)
            else:
                self.overlay_animate(opacity = 1, offset = 0)
            self.overlay_active = not self.overlay_active
            return True
        # Allow touches through to child widgets (e.g. Hourly/Daily toggle)
        return super(WeatherWidget, self).on_touch_down(touch)
    
    def overlay_animate(self, opacity = 1, offset = 0):
        animation = Animation(overlay_opacity = opacity, t='linear', d=0.5)
        animation &= Animation(overlay_y_offset = offset, t='out_elastic', d=2)
        animation.start(self)

    def animate_in(self):
        animation = Animation(y_offset = 0, t='out_elastic', d=2)
        animation.start(self)

    def on_config_update(self, config):
        weather_enabled = CONFIG.get_int("weather", "enabled", 0)
        if weather_enabled == 1:
            self.opacity = 1
            # Re-read credentials in case they changed
            api_key = CONFIG.get("weather", "api_key", "")
            lat = CONFIG.get("weather", "latitude", "0")
            lon = CONFIG.get("weather", "longitude", "0")
            if api_key and not WEATHER.data_avail:
                WEATHER.enabled = 1
                WEATHER.api_key = api_key
                WEATHER.latitude = lat
                WEATHER.longitude = lon
                WEATHER.register_weather_api_call(
                    WEATHER.api_url.format(lat, lon, api_key),
                    WEATHER.interval,
                    WEATHER.update_weather
                )
            if self._clock_event is None:
                self._clock_event = Clock.schedule_interval(lambda _: self.update(), 1)
                PIHOME_LOGGER.info("WeatherWidget: clock started after config update")
        else:
            self.opacity = 0
            if self._clock_event is not None:
                self._clock_event.cancel()
                self._clock_event = None
                PIHOME_LOGGER.info("WeatherWidget: clock stopped after config update")
        self._apply_theme_colors()
        for widget in self.walk():
            if isinstance(widget, WeatherDetails):
                widget.on_config_update(config)

    def update(self):
        try:
            self.temp = str(round(WEATHER.temperature))
            self.uvIndex = str(WEATHER.uv_index)
            self.pill_icon = ""

            try:
                uv_val = float(WEATHER.uv_index)
                if uv_val > 5:
                    self.pill_stat = "UV {}".format(int(uv_val))
                    if uv_val > 7:
                        self.pill_icon = '\ue002'
                        self.pill_stat_color = [0.96, 0.38, 0.32, 1.0]
                    else:
                        self.pill_icon = '\ue000'
                        self.pill_stat_color = list(self.text_color)
                else:
                    self.pill_icon = '\ue798'
                    self.pill_stat = "{}%".format(WEATHER.precip_propability)
                    self.pill_stat_color = list(self.text_color)
            except Exception:
                pass
            self.windSpeed = "{} MPH".format(WEATHER.wind_speed)
            self.precipPercent = "{}%".format(WEATHER.precip_propability)
            self.humidity = "{}%".format(WEATHER.humidity)
            self.airQuality = WEATHER.epa_air_lookup[WEATHER.epa_air_quality]
            self.airQuality = "NA"
            self.sunrise = "{}".format(WEATHER.sunrise_time)
            self.sunset = "{}".format(WEATHER.sunset_time)
            self.feelsLike = "{}".format(WEATHER.feels_like)
            self.cloudCover = "{}%".format(WEATHER.cloud_cover)
            self.future = WEATHER.future
            self.future_daily = WEATHER.future_daily
            self.day = WEATHER.future[1]
            self._rebuild_forecast()

            conf = get_app().web_conf
            if conf != None:
                host = conf["host"]
                path = conf["weather_icons"]
                day_code = 0
                if WEATHER.is_currently_day() == False:
                    day_code = 1
                self.icon = "{}{}{}{}.png".format(host, path, str(WEATHER.weather_code), str(day_code))
                self.icon_large = "{}{}{}{}_large@2x.png".format(host, path, str(WEATHER.weather_code), str(day_code))
                self.icon_fallback = "{}{}{}{}.png".format(host, path, str(WEATHER.weather_code), 0)
                self.icon_fallback_large = "{}{}{}{}_large@2x.png".format(host, path, str(WEATHER.weather_code), 0)
                self.dayIcon = "{}{}{}.png".format(host, path, str(WEATHER.weather_code_day))
                self.nightIcon = "{}{}{}.png".format(host, path, str(WEATHER.weather_code_night))

            if self.is_loaded is False:
                self.animate_in()
                self.is_loaded = True

            self._update_alerts()

        except Exception as e:
            PIHOME_LOGGER.error(e)

    # ── Forecast scroll ──

    def _rebuild_forecast(self):
        """Rebuild hourly/daily forecast widgets when data changes."""
        hourly_data = self.future[:24]  # cap at 24 hours
        daily_data = self.future_daily

        # Only rebuild if count changed (data updates within same count
        # are handled by existing WeatherDetails clock intervals)
        if len(hourly_data) != self._hourly_count:
            self._hourly_count = len(hourly_data)
            container = self.ids.get("hourly_container")
            if container:
                container.clear_widgets()
                widgets = []
                for item in hourly_data:
                    wd = WeatherDetails(details=item)
                    container.add_widget(wd)
                    widgets.append(wd)
                self._set_next_temps(widgets, hourly_data)

        if len(daily_data) != self._daily_count:
            self._daily_count = len(daily_data)
            container = self.ids.get("daily_container")
            if container:
                container.clear_widgets()
                widgets = []
                for item in daily_data:
                    wd = WeatherDetails(details=item, is_daily=True)
                    container.add_widget(wd)
                    widgets.append(wd)
                self._set_next_temps(widgets, daily_data)

    @staticmethod
    def _set_next_temps(widgets, data):
        """Set next_temp_value on each WeatherDetails for the trend line."""
        for i, wd in enumerate(widgets):
            try:
                if i < len(data) - 1:
                    wd.next_temp_value = data[i + 1]["values"]["temperature"]
                else:
                    wd.next_temp_value = data[i]["values"]["temperature"]
            except (KeyError, TypeError):
                pass

    # ── Alert carousel ──

    SEVERITY_COLORS = {
        Severity.EXTREME:  [0.80, 0.15, 0.15, 1.0],  # red
        Severity.SEVERE:   [0.90, 0.40, 0.15, 1.0],  # orange
        Severity.MODERATE: [0.90, 0.75, 0.20, 1.0],  # yellow
        Severity.MINOR:    [0.30, 0.70, 0.90, 1.0],  # blue
        Severity.UNKNOWN:  [0.50, 0.50, 0.50, 1.0],  # gray
    }

    SEVERITY_ICONS = {
        Severity.EXTREME:  "\ue000",  # error
        Severity.SEVERE:   "\ue002",  # warning
        Severity.MODERATE: "\ue88e",  # info
        Severity.MINOR:    "\ue88e",  # info
        Severity.UNKNOWN:  "\ue88e",  # info
    }

    def _get_alert_key(self, insight):
        """Generate a stable key for an insight to detect changes."""
        return (insight.insight, insight.severity,
                str(insight.start_time), str(insight.end_time),
                insight.title)

    def _update_alerts(self):
        """Sync the alert carousel with current WEATHER.insights."""
        insights = WEATHER.insights
        # Show active and upcoming alerts, sorted by severity (most severe first)
        relevant = [i for i in insights if i.is_active or i.is_upcoming]
        relevant = Insight.sort_by_severity(relevant, descending=True)

        new_keys = [self._get_alert_key(i) for i in relevant]
        if new_keys == self._last_alert_keys and self.alert_count == len(relevant):
            return  # no change
        self._last_alert_keys = new_keys

        carousel = self.ids.get("alert_carousel")
        dots_box = self.ids.get("alert_dots")
        if not carousel or not dots_box:
            return

        # Clear existing slides
        carousel.clear_widgets()
        dots_box.clear_widgets()

        self.alert_count = len(relevant)

        if not relevant:
            self.alert_opacity = 0
            return

        # Build slides
        for insight in relevant:
            slide = self._build_alert_slide(insight)
            carousel.add_widget(slide)

        # Build dots
        self._rebuild_dots(dots_box, len(relevant), 0)

        # Unbind any previous index listener, then rebind
        if hasattr(self, '_carousel_index_cb'):
            carousel.unbind(index=self._carousel_index_cb)
        count = len(relevant)
        self._carousel_index_cb = lambda inst, idx, c=count: self._rebuild_dots(dots_box, c, idx)
        carousel.bind(index=self._carousel_index_cb)

        # Animate in
        if self.alert_opacity == 0:
            Animation(alert_opacity=1, t='linear', d=0.4).start(self)

    def _rebuild_dots(self, dots_box, count, active_idx):
        """Rebuild the page indicator dots."""
        dots_box.clear_widgets()
        for i in range(count):
            is_active = (i == active_idx)
            dot = Widget(size_hint=(None, None), size=(dp(8), dp(8)))
            alpha = 0.9 if is_active else 0.3
            with dot.canvas:
                Color(1, 1, 1, alpha)
                Ellipse(pos=dot.pos, size=dot.size)
            # Bind pos so the ellipse follows layout changes (use default arg to capture)
            dot.bind(pos=lambda w, p, a=is_active: self._redraw_dot(w, a))
            dots_box.add_widget(dot)

    def _redraw_dot(self, widget, is_active):
        """Redraw a single dot after layout."""
        widget.canvas.clear()
        alpha = 0.9 if is_active else 0.3
        with widget.canvas:
            Color(1, 1, 1, alpha)
            Ellipse(pos=widget.pos, size=widget.size)

    def _build_alert_slide(self, insight):
        """Build a single alert card widget for the carousel."""
        sev_color = self.SEVERITY_COLORS.get(insight.severity, self.SEVERITY_COLORS[Severity.UNKNOWN])
        sev_icon = self.SEVERITY_ICONS.get(insight.severity, "\ue88e")
        dark = Theme().mode == 1

        # -- Outer container (centers the card in the slide) --
        container = FloatLayout(size_hint=(1, 1))

        card_width = min(Window.width - dp(80), dp(500))
        card_height = dp(160)

        card = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            size=(card_width, card_height),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            padding=[dp(20), dp(16), dp(20), dp(16)],
            spacing=dp(6),
        )

        # Card background
        is_extreme = (insight.severity == Severity.EXTREME)
        bg_color = [0.10, 0.12, 0.16, 0.95] if dark else [0.96, 0.96, 0.97, 0.95]
        border_color = sev_color[:3] + [1]

        # For extreme alerts, store a mutable alpha ref for the pulsing border
        border_alpha = [0.8] if is_extreme else [None]
        # Color instruction ref for the border so we can update its alpha
        border_color_instr = [None]

        border_width = 12 if is_extreme else 10
        half_bw = border_width / 2.0

        def update_card_bg(widget, *args):
            widget.canvas.before.clear()
            with widget.canvas.before:
                # Fill
                Color(*bg_color)
                RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(16)])
                # Border — inset by half the stroke width so it stays on the edge
                if is_extreme:
                    c = Color(sev_color[0], sev_color[1], sev_color[2], border_alpha[0])
                    border_color_instr[0] = c
                else:
                    Color(*border_color)
                Line(
                    rounded_rectangle=[
                        widget.pos[0] + half_bw,
                        widget.pos[1] + half_bw,
                        widget.size[0] - border_width,
                        widget.size[1] - border_width,
                        dp(20)
                    ],
                    width=border_width,
                )
        card.bind(pos=update_card_bg, size=update_card_bg)

        # Pulse the border for extreme severity
        if is_extreme:
            def _pulse_border(dt):
                import math
                t = Clock.get_boottime()
                # Oscillate alpha between 0.15 and 0.85
                alpha = 0.15 + 0.70 * (0.5 + 0.5 * math.sin(t * 3.5))
                border_alpha[0] = alpha
                if border_color_instr[0] is not None:
                    border_color_instr[0].a = alpha
            card._pulse_event = Clock.schedule_interval(_pulse_border, 1 / 30.0)

            # Clean up when card is removed from widget tree
            def _on_parent(widget, parent):
                if parent is None and hasattr(widget, '_pulse_event'):
                    widget._pulse_event.cancel()
            card.bind(parent=_on_parent)

        # -- Row 1: icon + title + severity badge --
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(28), spacing=dp(8))

        icon_lbl = Label(
            text=sev_icon,
            font_name='MaterialIcons',
            font_size=sp(20),
            color=sev_color,
            size_hint_x=None,
            width=dp(24),
            halign='center',
            valign='middle',
        )
        icon_lbl.text_size = (dp(24), None)
        header.add_widget(icon_lbl)

        title_text = insight.title or insight.insight.replace("_", " ").title()
        title_lbl = Label(
            text=title_text,
            font_name='Nunito',
            font_size=sp(14),
            bold=True,
            color=self.text_color,
            halign='left',
            valign='middle',
            shorten=True,
            shorten_from='right',
        )
        title_lbl.bind(size=lambda w, s: setattr(w, 'text_size', (w.width, None)))
        header.add_widget(title_lbl)

        # Severity badge
        badge_text = insight.severity.upper()
        badge = Label(
            text=badge_text,
            font_name='Nunito',
            font_size=sp(10),
            bold=True,
            color=sev_color,
            size_hint_x=None,
            width=dp(70),
            halign='right',
            valign='middle',
        )
        badge.text_size = (dp(70), None)
        header.add_widget(badge)

        card.add_widget(header)

        # -- Row 2: description --
        desc_text = insight.description or ""
        if len(desc_text) > 200:
            desc_text = desc_text[:197] + "..."

        if desc_text:
            desc_lbl = Label(
                text=desc_text,
                font_name='Nunito',
                font_size=sp(11),
                color=self.text_color[:3] + [0.7],
                halign='left',
                valign='top',
                size_hint_y=1,
            )
            desc_lbl.bind(size=lambda w, s: setattr(w, 'text_size', (w.width, w.height)))
            card.add_widget(desc_lbl)
        else:
            card.add_widget(Widget())  # spacer

        # -- Row 3: time info + origin --
        footer = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(20), spacing=dp(8))

        time_str = self._format_alert_time(insight)
        time_lbl = Label(
            text=time_str,
            font_name='Nunito',
            font_size=sp(10),
            color=self.text_color[:3] + [0.45],
            halign='left',
            valign='middle',
        )
        time_lbl.bind(size=lambda w, s: setattr(w, 'text_size', (w.width, None)))
        footer.add_widget(time_lbl)

        if insight.origin:
            origin_lbl = Label(
                text=insight.origin,
                font_name='Nunito',
                font_size=sp(10),
                color=self.text_color[:3] + [0.35],
                size_hint_x=None,
                width=dp(60),
                halign='right',
                valign='middle',
            )
            origin_lbl.text_size = (dp(60), None)
            footer.add_widget(origin_lbl)

        card.add_widget(footer)

        container.add_widget(card)
        return container

    def _format_alert_time(self, insight):
        """Format a human-readable time string for an alert."""
        now = datetime.now(timezone.utc)
        parts = []
        if insight.is_active:
            parts.append("Active now")
            if insight.end_time:
                delta = insight.end_time - now
                hours = int(delta.total_seconds() / 3600)
                if hours > 0:
                    parts.append("ends in {}h".format(hours))
                else:
                    mins = max(1, int(delta.total_seconds() / 60))
                    parts.append("ends in {}m".format(mins))
        elif insight.is_upcoming:
            if insight.start_time:
                delta = insight.start_time - now
                hours = int(delta.total_seconds() / 3600)
                if hours > 24:
                    parts.append("Starts in {}d".format(hours // 24))
                elif hours > 0:
                    parts.append("Starts in {}h".format(hours))
                else:
                    mins = max(1, int(delta.total_seconds() / 60))
                    parts.append("Starts in {}m".format(mins))
        if insight.duration_hours is not None:
            parts.append("Duration: {}h".format(round(insight.duration_hours, 1)))
        return "  |  ".join(parts) if parts else ""