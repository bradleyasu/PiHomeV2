import threading
import time

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty, ColorProperty, NumericProperty, StringProperty,
)

from components.NumberStepper.numberstepper import NumberStepper
from interface.pihomescreen import PiHomeScreen
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

from services.emporia.emporia_service import EMPORIA_SERVICE
from screens.EmporiumPower.barchart import BarChart  # noqa: F401  (registers with Factory for KV)
from screens.EmporiumPower.devicerow import DeviceRow

Builder.load_file("./screens/EmporiumPower/emporiumpower.kv")

_HOME_KEY = "__home__"

# Emporia "virtual" channels that report live usage but are rejected (HTTP 400) by
# the historical getChartUsage endpoint, so we don't try to chart them.
_NON_CHARTABLE = {"balance", "totalusage", "mainsfromgrid", "mainstogrid"}

# Chart results are cached only briefly. PiHome runs for days/weeks without restart,
# so a permanent cache would keep serving an old "today" after the date rolls over.
# A short TTL also lets today's (growing) bar refresh on its own.
_CHART_TTL = 300  # seconds

_STATUS_OK   = [0.30, 0.80, 0.45, 1]
_STATUS_ERR  = [0.90, 0.32, 0.32, 1]
_STATUS_IDLE = [0.45, 0.45, 0.45, 1]


class EmporiumPowerScreen(PiHomeScreen):
    """Live home power usage from an Emporia Vue monitor, with a per-circuit
    ranking (ordered by live watts) and a daily usage-trend chart.

    Live data and chart fetches come from the always-on EMPORIA_SERVICE so a
    single PyEmVue session is shared and monitoring keeps running off-screen.
    """

    # ── Theme colors ──
    bg_color     = ColorProperty([0.10, 0.10, 0.12, 1])
    header_color = ColorProperty([0.14, 0.14, 0.16, 1])
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([1, 1, 1, 0.45])
    accent_color = ColorProperty([0.25, 0.52, 1.0, 1])
    status_color = ColorProperty(_STATUS_IDLE)
    card_color   = ColorProperty([0.14, 0.14, 0.16, 0.85])

    # ── Display properties ──
    total_watts_text = StringProperty("-- W")
    chart_title_text = StringProperty("Whole Home")
    chart_total_text = StringProperty("")
    range_days       = NumericProperty(7)
    message_text     = StringProperty("")
    show_message     = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._channel_objs = {}     # (gid, channel_num) -> usage channel object (from snapshot)
        self._home_channel = None   # main channel object (from snapshot)
        self._chart_cache = {}      # (selected_key, days) -> (vals, labels)
        self._selected_key = _HOME_KEY
        self._charted = False

        self._rows = []
        self._home_row = None
        self._stepper = None

        self._load_config()
        self.range_days = self._default_days
        Clock.schedule_once(self._build, 0)

    # ── Build dynamic widgets ──

    def _build(self, *_):
        self._home_row = DeviceRow(device_name="Whole Home")
        # NOTE: on_pressed must be assigned AFTER construction. Passing on_pressed=...
        # as a kwarg makes Kivy treat it as an event binding, not an ObjectProperty set,
        # leaving self.on_pressed == None so taps never fire.
        self._home_row.on_pressed = self._on_row_selected
        self._home_row._key = _HOME_KEY
        self.ids.home_holder.add_widget(self._home_row)

        self._stepper = NumberStepper(
            on_change=self._on_range_changed,
            value=int(self.range_days), min_val=1, max_val=30, unit="d",
        )
        self.ids.stepper_holder.add_widget(self._stepper)

        self._apply_theme_to_children()

    # ── Configuration ──

    def _load_config(self):
        self._email = CONFIG.get("emporiumpower", "email", "").strip()
        self._password = CONFIG.get("emporiumpower", "password", "").strip()
        self._default_days = min(30, max(1, CONFIG.get_int("emporiumpower", "default_days", 7)))
        self._enabled = CONFIG.get("emporiumpower", "enabled", "0").strip().lower() in ("1", "true")

    def on_config_update(self, config):
        old = (self._email, self._password, self._enabled)
        self._load_config()
        if self.is_open and (self._email, self._password, self._enabled) != old:
            self._chart_cache.clear()
            self._charted = False
            EMPORIA_SERVICE.remove_listener(self._on_snapshot)
            Clock.schedule_once(lambda dt: self._enter(), 0.3)
        super().on_config_update(config)
        self._apply_theme_to_children()

    # ── Lifecycle ──

    def on_enter(self, *args):
        self._load_config()
        self._enter()
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        EMPORIA_SERVICE.remove_listener(self._on_snapshot)
        return super().on_pre_leave(*args)

    def _enter(self):
        if not EMPORIA_SERVICE.available:
            self._set_status(_STATUS_ERR)
            self._set_message("The 'pyemvue' package is not installed.\nRun:  pip install pyemvue")
            return
        if not self._enabled or not self._email or not self._password:
            self._set_status(_STATUS_IDLE)
            self._set_message("Add your Emporia email & password in\nSettings > Emporia Power, then enable it.")
            return

        EMPORIA_SERVICE.add_listener(self._on_snapshot)
        snap = EMPORIA_SERVICE.get_snapshot()
        if snap and snap.get("ok"):
            self._on_snapshot(snap)
        else:
            self._set_status(_STATUS_IDLE)
            self._set_message("Connecting to Emporia...")

    # ── Snapshot from the service (main thread) ──

    def _on_snapshot(self, snap):
        if not snap or not snap.get("ok"):
            return
        self._channel_objs = dict(snap.get("channels", {}))
        self._home_channel = snap.get("home_channel")

        home_watts = snap.get("home_watts", 0.0)
        self.total_watts_text = self._fmt_watts(home_watts)
        if self._home_row is not None:
            self._home_row.watts = home_watts
            self._home_row.watts_text = self._fmt_watts(home_watts)
            self._home_row.selected = (self._selected_key == _HOME_KEY)

        self._rebuild_rows(snap.get("rows", []))
        self._set_status(_STATUS_OK)
        self._set_message("")
        self._maybe_refresh_chart()

    def _maybe_refresh_chart(self):
        """Render the chart on first data, and thereafter only refetch when our
        cached entry for the current view has expired (e.g. the day rolled over)."""
        if not self._charted:
            self._charted = True
            self._refresh_chart()
            return
        cache_key = (self._selected_key, int(self.range_days))
        cached = self._chart_cache.get(cache_key)
        if not cached or (time.time() - cached[0] >= _CHART_TTL):
            self._refresh_chart()

    def _rebuild_rows(self, rows):
        box = self.ids.list_box
        box.clear_widgets()
        self._rows = []
        max_w = max((r["watts"] for r in rows), default=0.0) or 1.0
        for r in rows:
            row = DeviceRow(
                device_name=r["name"],
                watts=r["watts"],
                watts_text=self._fmt_watts(r["watts"]),
                fraction=r["watts"] / max_w,
                selected=(r["key"] == self._selected_key),
                text_color=self.text_color,
                muted_color=self.muted_color,
                accent_color=self.accent_color,
                divider_color=(1, 1, 1, 0.07),
            )
            # Assign after construction — see note in _build (on_pressed as kwarg won't set).
            row.on_pressed = self._on_row_selected
            row._key = r["key"]
            row._channel = r.get("channel")
            box.add_widget(row)
            self._rows.append(row)

    # ── Selection & chart ──

    def _on_row_selected(self, row):
        self._selected_key = getattr(row, "_key", _HOME_KEY)
        if self._home_row is not None:
            self._home_row.selected = (self._selected_key == _HOME_KEY)
        for r in self._rows:
            r.selected = (getattr(r, "_key", None) == self._selected_key)
        self._refresh_chart()

    def _refresh_chart(self, force=False):
        if not EMPORIA_SERVICE.available:
            return
        if self._selected_key == _HOME_KEY:
            channel = self._home_channel
            title = "Whole Home"
        else:
            channel = self._channel_objs.get(self._selected_key)
            row = next((r for r in self._rows if getattr(r, "_key", None) == self._selected_key), None)
            if channel is None and row is not None:
                channel = getattr(row, "_channel", None)
            title = row.device_name if row else "Circuit"
        if channel is None:
            PIHOME_LOGGER.warn(f"EmporiumPower: no channel object for {self._selected_key}; cannot chart")
            return

        if str(getattr(channel, "channel_num", "")).lower() in _NON_CHARTABLE:
            # e.g. the "Balance" pseudo-channel — live watts exist but no daily history.
            self.chart_title_text = title
            self.ids.chart.data = []
            self.ids.chart.labels = []
            self.chart_total_text = "Daily trend not available for this channel"
            return

        days = int(self.range_days)
        cache_key = (self._selected_key, days)
        if force:
            self._chart_cache.pop(cache_key, None)
        else:
            cached = self._chart_cache.get(cache_key)
            if cached and (time.time() - cached[0] < _CHART_TTL):
                _ts, vals, labels = cached
                self._apply_chart(vals, labels, title, self._selected_key, days)
                return

        self.chart_title_text = title
        threading.Thread(
            target=self._chart_worker, args=(channel, days, self._selected_key, title),
            daemon=True, name="emporia-chart",
        ).start()

    def _chart_worker(self, channel, days, key, title):
        vals, labels = EMPORIA_SERVICE.get_chart_usage(channel, days)
        if vals is None:
            Clock.schedule_once(lambda dt: self._set_status(_STATUS_ERR), 0)
            return
        self._chart_cache[(key, days)] = (time.time(), vals, labels)
        Clock.schedule_once(lambda dt: self._apply_chart(vals, labels, title, key, days), 0)

    def _apply_chart(self, vals, labels, title, key, days):
        # Ignore stale results if the user has since changed selection/range.
        if key != self._selected_key or days != int(self.range_days):
            return
        self.ids.chart.data = vals
        self.ids.chart.labels = labels
        self.chart_title_text = title
        total = sum(vals)
        self.chart_total_text = f"{total:.1f} kWh over {days}d"

    def _on_range_changed(self, value):
        self.range_days = int(value)
        self._refresh_chart()

    # ── Theme / status / formatting ──

    def _apply_theme_to_children(self, *_):
        if self.ids.get("chart") is not None:
            self.ids.chart.bar_color = self.accent_color
            self.ids.chart.axis_color = (1, 1, 1, 0.18)
            self.ids.chart.label_color = self.muted_color
        if self._stepper is not None:
            self._stepper.accent_color = self.accent_color
            self._stepper.text_color = self.text_color
        for row in ([self._home_row] if self._home_row else []) + self._rows:
            row.text_color = self.text_color
            row.muted_color = self.muted_color
            row.accent_color = self.accent_color

    def _set_status(self, color):
        self.status_color = color

    def _set_message(self, text):
        self.message_text = text
        self.show_message = bool(text)

    @staticmethod
    def _fmt_watts(watts):
        if watts >= 1000:
            return f"{watts / 1000:.2f} kW"
        return f"{watts:.0f} W"

    # ── Rotary encoder ──

    def on_rotary_turn(self, direction, button_pressed):
        new_days = min(30, max(1, int(self.range_days) + direction))
        if new_days != int(self.range_days):
            self.range_days = new_days
            if self._stepper is not None:
                self._stepper.value = new_days
            self._refresh_chart()
        return True

    def on_rotary_pressed(self):
        self._refresh_chart(force=True)
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True
