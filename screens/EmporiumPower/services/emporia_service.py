"""Always-on Emporia Vue power monitor.

Authenticates to Emporia once, polls live per-circuit usage 24/7 (independent of
which screen is open), and evaluates user-defined threshold rules. When a device's
live watts crosses a rule's limit (rising or falling edge, with a per-rule
cooldown), the rule's nested PiHome event is fired.

Rules live in a shared :class:`~util.rulestore.RuleStore` (persistence, enable/
disable, cooldown, last-fired and firing); this service only detects the
threshold crossing and keeps the rising/falling-edge latch in its own state file.
Rules are managed via JSON events (see screens/EmporiumPower/events/) over
MQTT/HTTP/WebSocket and appear on the Automations screen. The EmporiumPower
screen consumes this service's snapshot instead of running its own poller
(single PyEmVue instance, no token-file races).

The fired event may interpolate ``$device`` ``$watts`` ``$limit`` ``$direction``.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from kivy.clock import Clock

from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER
from util.rulestore import RuleStore

try:
    from pyemvue import PyEmVue
    from pyemvue.enums import Scale, Unit
except Exception:  # ImportError or any transitive import error
    PyEmVue = None
    Scale = None
    Unit = None

_TOKEN_FILE = "cache/emporia_tokens.json"
_STATE_FILE = "cache/emporia_alerts_state.json"


def _describe(rule):
    """Human-readable trigger text for the Automations screen."""
    return (f"{rule.get('device', '?')} goes {rule.get('direction', 'above')} "
            f"{rule.get('limit', '?')}W")


# Rule storage, validation, cooldown and firing all live in the shared store —
# this service only detects the threshold crossing.
RULES = RuleStore(
    key="emporia",
    label="Power",
    path="cache/emporia_alerts.json",
    glyph="",          # flash_on
    describe=_describe,
    create_event="emporia_power_alert",
)

# Channel numbers Emporia uses for the whole-home (summed mains) total.
_MAIN_CHANNELS = ("1,2,3", "1,2,3,4")
# Names a rule may use to target the whole-home total.
_HOME_ALIASES = ("whole home", "wholehome", "home", "total", "mains", "main")

# Emporia "virtual" channels that report live usage but are rejected (HTTP 400) by
# the historical getChartUsage endpoint.
_NON_CHARTABLE = {"balance", "totalusage", "mainsfromgrid", "mainstogrid"}

# Cost/energy totals change slowly, so we refresh them on their own (slower)
# cadence rather than on every live-watts poll.
_COST_INTERVAL = 300  # seconds


class EmporiaService:
    def __init__(self):
        self._vue = None
        self._vue_lock = threading.Lock()       # serialize all PyEmVue calls
        self._stop = threading.Event()

        self._all_gids = []
        self._cost = {"today": None, "month": None, "projected": None, "rate_cents": 0.0}
        self._today_by_key = {}        # (gid, chnum) -> {"kwh": float, "cost": float}
        self._last_cost_fetch = 0.0
        self._rate_cents = 0.0
        self._billing_start_day = 1
        self._snapshot = {"ok": False, "rows": [], "home_watts": 0.0,
                          "channels": {}, "home_channel": None, "ts": 0,
                          "cost": self._cost, "today_by_key": self._today_by_key}
        self._listeners = []

        # Rule persistence/firing lives in RULES (the shared store); _state holds
        # only the rising/falling-edge latch, which is trigger state, not rule state.
        self._state = self._load_json(_STATE_FILE, {})    # id -> {was_over}

        self._thread = threading.Thread(target=self._run, daemon=True, name="emporia-service")
        self._thread.start()

    @property
    def available(self):
        return PyEmVue is not None

    # ── Config ──

    def _cfg(self):
        email = CONFIG.get("emporiumpower", "email", "").strip()
        password = CONFIG.get("emporiumpower", "password", "").strip()
        interval = max(15, CONFIG.get_int("emporiumpower", "refresh_interval", 30))
        enabled = CONFIG.get("emporiumpower", "enabled", "0").strip().lower() in ("1", "true")
        return email, password, interval, enabled

    # ── Persistence helpers ──

    def _load_json(self, path, default):
        try:
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f) or default
        except Exception as e:
            PIHOME_LOGGER.error(f"Emporia: failed to read {path}: {e}")
        return default

    def _save_json(self, path, data):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            PIHOME_LOGGER.error(f"Emporia: failed to write {path}: {e}")

    # ── Auth ──

    def _authenticate(self, email, password):
        """Login with cached tokens for a fast start, always passing username/password
        so pyemvue can auto re-authenticate when the Cognito refresh token expires."""
        try:
            vue = PyEmVue()
            os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
            cached = self._load_json(_TOKEN_FILE, {})
            try:
                vue.login(
                    username=email, password=password,
                    id_token=cached.get("id_token"),
                    access_token=cached.get("access_token"),
                    refresh_token=cached.get("refresh_token"),
                    token_storage_file=_TOKEN_FILE,
                )
            except Exception as e:
                PIHOME_LOGGER.warn(f"Emporia: token login failed ({e}); retrying with credentials")
                vue.login(username=email, password=password, token_storage_file=_TOKEN_FILE)
            self._vue = vue
            return True
        except Exception as e:
            PIHOME_LOGGER.error(f"Emporia: authentication failed: {e}")
            return False

    # ── Poll loop ──

    def _run(self):
        if PyEmVue is None:
            PIHOME_LOGGER.warn("Emporia: pyemvue not installed; monitor idle")
            return
        while not self._stop.is_set():
            email, password, interval, enabled = self._cfg()
            if not enabled or not email or not password:
                self._stop.wait(10)
                continue
            if self._vue is None and not self._authenticate(email, password):
                self._stop.wait(30)
                continue
            if not self._all_gids:
                try:
                    with self._vue_lock:
                        devices = self._vue.get_devices()
                    self._all_gids = [d.device_gid for d in devices]
                    self._capture_meta(devices)
                except Exception as e:
                    PIHOME_LOGGER.error(f"Emporia: get_devices failed: {e}")
                    self._vue = None
                    self._stop.wait(30)
                    continue
            try:
                with self._vue_lock:
                    usage = self._vue.get_device_list_usage(
                        deviceGids=self._all_gids,
                        instant=datetime.now(timezone.utc),
                        scale=Scale.MINUTE.value, unit=Unit.KWH.value,
                    )
                self._apply_usage(usage)
            except Exception as e:
                PIHOME_LOGGER.error(f"Emporia: usage poll failed: {e}")
                self._vue = None  # force re-auth / re-fetch next cycle
            if self._vue is not None and time.time() - self._last_cost_fetch >= _COST_INTERVAL:
                self._fetch_costs()
            self._stop.wait(interval)

    def _apply_usage(self, usage):
        rows = []
        home_watts = None
        home_channel = None
        channels = {}            # (gid, chnum) -> usage channel object
        watts_by_name = {}       # lower name -> watts (for rule evaluation)
        for gid, udev in (usage or {}).items():
            for chnum, chu in (getattr(udev, "channels", {}) or {}).items():
                watts = (getattr(chu, "usage", None) or 0.0) * 60000.0
                if str(chnum) in _MAIN_CHANNELS:
                    home_watts = watts
                    home_channel = chu
                    continue
                name = (getattr(chu, "name", "") or "").strip()
                if not name or name.lower() == "main":
                    name = f"Circuit {chnum}"
                key = (str(gid), str(chnum))
                channels[key] = chu
                rows.append({"key": key, "name": name, "watts": watts, "channel": chu})
                watts_by_name[name.lower()] = watts

        if home_watts is None:
            home_watts = sum(r["watts"] for r in rows)
        rows.sort(key=lambda r: r["watts"], reverse=True)

        for alias in _HOME_ALIASES:
            watts_by_name[alias] = home_watts

        self._snapshot = {
            "ok": True, "rows": rows, "home_watts": home_watts,
            "channels": channels, "home_channel": home_channel, "ts": time.time(),
            "cost": self._cost, "today_by_key": self._today_by_key,
        }
        self._evaluate_rules(watts_by_name)
        self._notify()

    # ── Cost / energy totals (slow cadence) ──

    def _capture_meta(self, devices):
        """Capture the utility rate and billing-cycle start day from device metadata."""
        for d in devices or []:
            rate = getattr(d, "usage_cent_per_kw_hour", None) or 0.0
            if rate > 0:
                self._rate_cents = float(rate)
            start = getattr(d, "billing_cycle_start_day", None) or 0
            if start:
                self._billing_start_day = int(start)

    def _main_value(self, usage):
        """Return the whole-home (summed mains) value from a usage response."""
        for _gid, udev in (usage or {}).items():
            for chnum, chu in (getattr(udev, "channels", {}) or {}).items():
                if str(chnum) in _MAIN_CHANNELS:
                    return getattr(chu, "usage", None) or 0.0
        return 0.0

    def _fetch_costs(self):
        """Fetch slow-changing totals (today/month cost, per-circuit today cost & kWh)
        and merge them into the snapshot. Runs in the service poll thread."""
        try:
            now = datetime.now(timezone.utc)
            with self._vue_lock:
                day_usd = self._vue.get_device_list_usage(
                    deviceGids=self._all_gids, instant=now,
                    scale=Scale.DAY.value, unit=Unit.USD.value)
                mon_usd = self._vue.get_device_list_usage(
                    deviceGids=self._all_gids, instant=now,
                    scale=Scale.MONTH.value, unit=Unit.USD.value)
                day_kwh = self._vue.get_device_list_usage(
                    deviceGids=self._all_gids, instant=now,
                    scale=Scale.DAY.value, unit=Unit.KWH.value)

            today_cost = self._main_value(day_usd)
            month_cost = self._main_value(mon_usd)

            by_key = {}
            for gid, udev in (day_usd or {}).items():
                for chnum, chu in (getattr(udev, "channels", {}) or {}).items():
                    if str(chnum) in _MAIN_CHANNELS:
                        continue
                    by_key.setdefault((str(gid), str(chnum)), {})["cost"] = \
                        getattr(chu, "usage", None) or 0.0
            for gid, udev in (day_kwh or {}).items():
                for chnum, chu in (getattr(udev, "channels", {}) or {}).items():
                    if str(chnum) in _MAIN_CHANNELS:
                        continue
                    by_key.setdefault((str(gid), str(chnum)), {})["kwh"] = \
                        getattr(chu, "usage", None) or 0.0

            self._cost = {
                "today": today_cost, "month": month_cost,
                "projected": self._project_month(month_cost),
                "rate_cents": self._rate_cents,
            }
            self._today_by_key = by_key
            self._last_cost_fetch = time.time()
            self._snapshot = {**self._snapshot, "cost": self._cost,
                              "today_by_key": self._today_by_key}
            self._notify()
        except Exception as e:
            PIHOME_LOGGER.error(f"Emporia: cost fetch failed: {e}")

    def _project_month(self, mtd_cost):
        """Extrapolate the month-to-date cost across the full billing cycle."""
        if not mtd_cost:
            return mtd_cost or 0.0
        today = datetime.now().astimezone().date()
        sd = min(max(1, self._billing_start_day), 28)
        if today.day >= sd:
            cycle_start = today.replace(day=sd)
        else:
            first = today.replace(day=1)
            cycle_start = (first - timedelta(days=1)).replace(day=sd)
        if cycle_start.month == 12:
            nxt = cycle_start.replace(year=cycle_start.year + 1, month=1)
        else:
            nxt = cycle_start.replace(month=cycle_start.month + 1)
        total_days = (nxt - cycle_start).days
        elapsed = (today - cycle_start).days + 1
        if elapsed <= 0:
            return mtd_cost
        return mtd_cost / elapsed * total_days

    # ── Rule evaluation (rising/falling edge + cooldown) ──

    def _evaluate_rules(self, watts_by_name):
        """Detect threshold crossings; the store owns cooldown and firing."""
        rules = RULES.list()["body"]["rules"]
        changed = False
        for rule in rules:
            rid = rule.get("id")
            dev = str(rule.get("device", "")).strip().lower()
            try:
                limit = float(rule.get("limit", 0))
            except (TypeError, ValueError):
                continue
            direction = str(rule.get("direction", "above")).lower()
            if dev not in watts_by_name:
                PIHOME_LOGGER.warn(f"Emporia alert '{rid}': device '{rule.get('device')}' not found this poll")
                continue

            watts = watts_by_name[dev]
            now_over = watts >= limit
            st = self._state.get(rid) or {"was_over": now_over}
            was_over = st.get("was_over", now_over)

            crossed = (direction == "above" and not was_over and now_over) or \
                      (direction == "below" and was_over and not now_over)
            if crossed:
                RULES.fire(rule, {
                    "device": rule.get("device"),
                    "watts": f"{watts:.0f}",
                    "limit": f"{limit:.0f}",
                    "direction": direction,
                })

            st["was_over"] = now_over
            self._state[rid] = st
            changed = True
        if changed:
            self._save_json(_STATE_FILE, self._state)

    # ── Public rule API (called by the rule-management events) ──

    def add_or_update_rule(self, rule):
        """Validate the threshold fields, then hand persistence to the shared store."""
        def _validate(stored):
            if not stored.get("id"):
                return "'id' is required"
            if not stored.get("device"):
                return "'device' is required"
            if stored.get("limit") is None:
                return "'limit' (watts) is required"
            if stored.get("direction") not in ("above", "below"):
                return "'direction' must be 'above' or 'below'"
            return None

        # Preserve this store's own defaults (300s cooldown, "above").
        prepared = dict(rule)
        prepared["direction"] = str(rule.get("direction", "above")).lower()
        if rule.get("cooldown") is None:
            prepared["cooldown"] = 300
        try:
            if prepared.get("limit") is not None:
                prepared["limit"] = float(prepared["limit"])
        except (TypeError, ValueError):
            return {"code": 400, "body": {
                "status": "error", "message": "'limit' must be a number"}}
        if prepared.get("device") is not None:
            prepared["device"] = str(prepared["device"])

        response = RULES.upsert(prepared, validate=_validate)
        if response["code"] == 200:
            # Reset the latch so stale edge state can't suppress or spuriously
            # fire the rule that was just saved.
            rid = response["body"]["id"]
            self._state.pop(rid, None)
            self._save_json(_STATE_FILE, self._state)
        return response

    def remove_rule(self, rid):
        response = RULES.remove(rid)
        if response["code"] == 200:
            self._state.pop(str(rid).strip(), None)
            self._save_json(_STATE_FILE, self._state)
        return response

    def list_rules(self):
        return RULES.list()

    # ── Snapshot / listeners (consumed by the screen) ──

    def get_snapshot(self):
        return self._snapshot

    def add_listener(self, cb):
        if cb not in self._listeners:
            self._listeners.append(cb)

    def remove_listener(self, cb):
        if cb in self._listeners:
            self._listeners.remove(cb)

    def _notify(self):
        snap = self._snapshot
        for cb in list(self._listeners):
            Clock.schedule_once(lambda dt, c=cb: self._safe_cb(c, snap), 0)

    def _safe_cb(self, cb, snap):
        try:
            cb(snap)
        except Exception as e:
            PIHOME_LOGGER.error(f"Emporia listener error: {e}")

    def get_chart_usage(self, channel, days):
        """Blocking — call from a background thread. Returns (vals, labels) or (None, None).

        Normalizes the API result onto a fixed axis of ``days`` local-calendar days
        ENDING TODAY. Emporia returns each channel's daily list starting at that
        channel's own first-data instant, so raw lists vary in length and end date
        between circuits. We instead map every returned daily value onto its real
        calendar date and lay it on a today-anchored axis, padding any missing day
        (including today) with 0. This keeps the x-axis identical across circuits and
        always ends on today's date.
        """
        if self._vue is None or Scale is None or channel is None:
            return None, None
        if str(getattr(channel, "channel_num", "")).lower() in _NON_CHARTABLE:
            # e.g. "Balance" — getChartUsage 400s for these virtual channels.
            return [], []
        try:
            # Align the request to LOCAL calendar days (so buckets match the wall
            # calendar) and extend the end to the start of tomorrow so today's
            # partial bucket is included in the response.
            local_now = datetime.now().astimezone()
            today = local_now.date()
            midnight = datetime.min.time()
            start_dt = datetime.combine(today - timedelta(days=days - 1), midnight).astimezone()
            end_dt = datetime.combine(today + timedelta(days=1), midnight).astimezone()

            with self._vue_lock:
                usage, first = self._vue.get_chart_usage(
                    channel, start=start_dt, end=end_dt,
                    scale=Scale.DAY.value, unit=Unit.KWH.value,
                )
            usage = usage or []

            # Map each returned daily value onto its local calendar date.
            by_date = {}
            if first is not None:
                if first.tzinfo is None:
                    first = first.replace(tzinfo=timezone.utc)
                first_local = first.astimezone()
                for i, v in enumerate(usage):
                    d = (first_local + timedelta(days=i)).date()
                    by_date[d] = float(v) if v is not None else 0.0

            axis = [today - timedelta(days=days - 1 - i) for i in range(days)]
            vals = [by_date.get(d, 0.0) for d in axis]
            labels = [d.strftime("%m/%d") for d in axis]
            return vals, labels
        except Exception as e:
            PIHOME_LOGGER.error(f"Emporia: chart fetch failed: {e}")
            return None, None


EMPORIA_SERVICE = EmporiaService()
