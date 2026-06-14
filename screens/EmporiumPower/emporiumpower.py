import json
import os
import threading
from datetime import datetime, timedelta, timezone

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty, ColorProperty, NumericProperty, StringProperty,
)

from components.NumberStepper.numberstepper import NumberStepper
from interface.pihomescreen import PiHomeScreen
from util.configuration import CONFIG
from util.helpers import toast
from util.phlog import PIHOME_LOGGER

from screens.EmporiumPower.barchart import BarChart  # noqa: F401  (registers with Factory for KV)
from screens.EmporiumPower.devicerow import DeviceRow

# pyemvue is an optional dependency — import lazily so the screen still loads
# (showing a helpful message) when the package isn't installed.
try:
    from pyemvue import PyEmVue
    from pyemvue.enums import Scale, Unit
except Exception:  # ImportError or any transitive import error
    PyEmVue = None
    Scale = None
    Unit = None

Builder.load_file("./screens/EmporiumPower/emporiumpower.kv")

# Cognito tokens are cached in the shared cache/ dir (same place as cocktail_cache.json,
# ha_favorites.json, etc.) so we don't re-login each launch.
_TOKEN_FILE = "cache/emporia_tokens.json"
# Channel numbers the Emporia API uses for the whole-home (summed mains) total.
_MAIN_CHANNELS = ("1,2,3", "1,2,3,4")
_HOME_KEY = "__home__"

_STATUS_OK    = [0.30, 0.80, 0.45, 1]
_STATUS_ERR   = [0.90, 0.32, 0.32, 1]
_STATUS_IDLE  = [0.45, 0.45, 0.45, 1]


class EmporiumPowerScreen(PiHomeScreen):
    """Live home power usage from an Emporia Vue monitor, with a per-circuit
    ranking (ordered by live watts) and a daily usage-trend chart."""

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
        self._stop_event = threading.Event()
        self._thread = None
        self._vue = None
        self._vue_lock = threading.Lock()

        self._devices = []
        self._all_gids = []
        self._channels = {}              # (gid, channel_num) -> VueDeviceChannel (from get_devices)
        self._whole_home_channel = None  # main channel from get_devices (used for first chart)
        self._channel_objs = {}          # key -> VueDeviceChannelUsage (live, from get_device_list_usage)
        self._home_channel = None        # main channel object from live usage
        self._chart_cache = {}           # (selected_key, days) -> (vals, labels)
        self._selected_key = _HOME_KEY

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
        self._refresh = max(15, CONFIG.get_int("emporiumpower", "refresh_interval", 30))
        self._default_days = min(30, max(1, CONFIG.get_int("emporiumpower", "default_days", 7)))
        self._enabled = CONFIG.get("emporiumpower", "enabled", "0").strip().lower() in ("1", "true")

    def on_config_update(self, config):
        old = (self._email, self._password, self._enabled)
        self._load_config()
        if self.is_open and (self._email, self._password, self._enabled) != old:
            self._chart_cache.clear()
            self._stop_work()
            Clock.schedule_once(lambda dt: self._enter(), 0.5)
        super().on_config_update(config)
        self._apply_theme_to_children()

    # ── Lifecycle ──

    def on_enter(self, *args):
        self._load_config()
        self._enter()
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        self._stop_work()
        return super().on_pre_leave(*args)

    def _enter(self):
        if not self._enabled or not self._email or not self._password:
            self._set_status(_STATUS_IDLE)
            self._set_message("Add your Emporia email & password in\nSettings > Emporia Power, then enable it.")
            return
        if PyEmVue is None:
            self._set_status(_STATUS_ERR)
            self._set_message("The 'pyemvue' package is not installed.\nRun:  pip install pyemvue")
            return
        self._set_message("")
        self._set_status(_STATUS_IDLE)
        self._start_work()

    # ── Background work ──

    def _start_work(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="emporia-worker"
        )
        self._thread.start()

    def _stop_work(self):
        self._stop_event.set()

    def _authenticate(self):
        """Login using cached tokens for a fast start, always passing the
        username/password so pyemvue can auto re-authenticate when the Cognito
        refresh token eventually expires. Returns True on success."""
        try:
            vue = PyEmVue()
            os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
            cached = {}
            if os.path.exists(_TOKEN_FILE):
                try:
                    with open(_TOKEN_FILE) as f:
                        cached = json.load(f) or {}
                except Exception:
                    cached = {}
            try:
                vue.login(
                    username=self._email, password=self._password,
                    id_token=cached.get("id_token"),
                    access_token=cached.get("access_token"),
                    refresh_token=cached.get("refresh_token"),
                    token_storage_file=_TOKEN_FILE,
                )
            except Exception as e:
                # Stale/corrupt token cache — fall back to a clean credential login.
                PIHOME_LOGGER.warn(f"EmporiumPower: token login failed ({e}); retrying with credentials")
                vue.login(
                    username=self._email, password=self._password,
                    token_storage_file=_TOKEN_FILE,
                )
            self._vue = vue
            return True
        except Exception as e:
            PIHOME_LOGGER.error(f"EmporiumPower: authentication failed: {e}")
            return False

    def _worker(self):
        if not self._authenticate():
            Clock.schedule_once(lambda dt: (
                self._set_status(_STATUS_ERR),
                toast("Emporia login failed", "error", 4),
                self._set_message("Login failed. Check your Emporia\nemail & password in Settings."),
            ), 0)
            return

        try:
            with self._vue_lock:
                devices = self._vue.get_devices()
        except Exception as e:
            PIHOME_LOGGER.error(f"EmporiumPower: get_devices failed: {e}")
            Clock.schedule_once(lambda dt: self._set_status(_STATUS_ERR), 0)
            return

        Clock.schedule_once(lambda dt, d=devices: self._apply_devices(d), 0)

        while not self._stop_event.is_set():
            try:
                with self._vue_lock:
                    usage = self._vue.get_device_list_usage(
                        deviceGids=self._all_gids,
                        instant=datetime.now(timezone.utc),
                        scale=Scale.MINUTE.value, unit=Unit.KWH.value,
                    )
                Clock.schedule_once(lambda dt, u=usage: self._apply_usage(u), 0)
                Clock.schedule_once(lambda dt: self._set_status(_STATUS_OK), 0)
            except Exception as e:
                PIHOME_LOGGER.error(f"EmporiumPower: usage poll failed: {e}")
                Clock.schedule_once(lambda dt: self._set_status(_STATUS_ERR), 0)
            self._stop_event.wait(self._refresh)

    # ── Apply data (main thread) ──

    def _apply_devices(self, devices):
        self._devices = devices
        self._all_gids = [d.device_gid for d in devices]
        self._channels = {}
        self._whole_home_channel = None
        for d in devices:
            for ch in getattr(d, "channels", []) or []:
                self._channels[(str(d.device_gid), str(ch.channel_num))] = ch
                if str(ch.channel_num) in _MAIN_CHANNELS and self._whole_home_channel is None:
                    self._whole_home_channel = ch
        if self._whole_home_channel is None and devices and getattr(devices[0], "channels", None):
            self._whole_home_channel = devices[0].channels[0]
        self._refresh_chart()

    def _apply_usage(self, usage):
        rows = []
        home_watts = None
        self._channel_objs = {}
        for gid, udev in (usage or {}).items():
            for chnum, chu in (getattr(udev, "channels", {}) or {}).items():
                watts = (getattr(chu, "usage", None) or 0.0) * 60000.0
                if str(chnum) in _MAIN_CHANNELS:
                    home_watts = watts
                    self._home_channel = chu  # live main-channel object for charting
                    continue
                name = (getattr(chu, "name", "") or "").strip()
                if not name or name.lower() == "main":
                    name = f"Circuit {chnum}"
                key = (str(gid), str(chnum))
                # The usage object IS a VueDeviceChannel (has device_gid + channel_num),
                # so keep it to pass straight to get_chart_usage — no fragile key matching.
                self._channel_objs[key] = chu
                rows.append({"key": key, "name": name, "watts": watts, "channel": chu})

        if home_watts is None:
            home_watts = sum(r["watts"] for r in rows)
        rows.sort(key=lambda r: r["watts"], reverse=True)

        self.total_watts_text = self._fmt_watts(home_watts)
        if self._home_row is not None:
            self._home_row.watts = home_watts
            self._home_row.watts_text = self._fmt_watts(home_watts)
            self._home_row.selected = (self._selected_key == _HOME_KEY)

        self._rebuild_rows(rows)
        self._set_message("")

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
            row._channel = r["channel"]
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
        if not self._devices or Scale is None:
            return
        if self._selected_key == _HOME_KEY:
            channel = self._home_channel or self._whole_home_channel
            title = "Whole Home"
        else:
            # Prefer the live usage channel object; fall back to the get_devices registry.
            channel = self._channel_objs.get(self._selected_key) or self._channels.get(self._selected_key)
            row = next((r for r in self._rows if getattr(r, "_key", None) == self._selected_key), None)
            if channel is None and row is not None:
                channel = getattr(row, "_channel", None)
            title = row.device_name if row else "Circuit"
        if channel is None:
            PIHOME_LOGGER.warn(f"EmporiumPower: no channel object for {self._selected_key}; cannot chart")
            return

        days = int(self.range_days)
        cache_key = (self._selected_key, days)
        if force:
            self._chart_cache.pop(cache_key, None)
        elif cache_key in self._chart_cache:
            vals, labels = self._chart_cache[cache_key]
            self._apply_chart(vals, labels, title, self._selected_key, days)
            return

        self.chart_title_text = title
        threading.Thread(
            target=self._chart_worker, args=(channel, days, self._selected_key, title),
            daemon=True, name="emporia-chart",
        ).start()

    def _chart_worker(self, channel, days, key, title):
        try:
            now = datetime.now(timezone.utc)
            with self._vue_lock:
                usage, start = self._vue.get_chart_usage(
                    channel, start=now - timedelta(days=days), end=now,
                    scale=Scale.DAY.value, unit=Unit.KWH.value,
                )
        except Exception as e:
            PIHOME_LOGGER.error(f"EmporiumPower: chart fetch failed: {e}")
            Clock.schedule_once(lambda dt: self._set_status(_STATUS_ERR), 0)
            return

        vals = [float(v) if v is not None else 0.0 for v in (usage or [])]
        base = start or (datetime.now(timezone.utc) - timedelta(days=days))
        labels = [(base + timedelta(days=i)).strftime("%m/%d") for i in range(len(vals))]
        self._chart_cache[(key, days)] = (vals, labels)
        Clock.schedule_once(
            lambda dt: self._apply_chart(vals, labels, title, key, days), 0
        )

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
