"""Always-on Emporia Vue power monitor.

Authenticates to Emporia once, polls live per-circuit usage 24/7 (independent of
which screen is open), and evaluates user-defined threshold rules. When a device's
live watts crosses a rule's limit (rising or falling edge, with a per-rule
cooldown), the rule's nested PiHome event is fired.

Rules are managed via JSON events (see screens/EmporiumPower/events/) over
MQTT/HTTP/WebSocket. Rules and per-rule latch state are persisted under cache/ so
they survive restarts. The EmporiumPower screen consumes this service's snapshot
instead of running its own poller (single PyEmVue instance, no token-file races).
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from kivy.clock import Clock

from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

try:
    from pyemvue import PyEmVue
    from pyemvue.enums import Scale, Unit
except Exception:  # ImportError or any transitive import error
    PyEmVue = None
    Scale = None
    Unit = None

_TOKEN_FILE = "cache/emporia_tokens.json"
_RULES_FILE = "cache/emporia_alerts.json"
_STATE_FILE = "cache/emporia_alerts_state.json"

# Channel numbers Emporia uses for the whole-home (summed mains) total.
_MAIN_CHANNELS = ("1,2,3", "1,2,3,4")
# Names a rule may use to target the whole-home total.
_HOME_ALIASES = ("whole home", "wholehome", "home", "total", "mains", "main")


class EmporiaService:
    def __init__(self):
        self._vue = None
        self._vue_lock = threading.Lock()       # serialize all PyEmVue calls
        self._rules_lock = threading.Lock()
        self._stop = threading.Event()

        self._all_gids = []
        self._snapshot = {"ok": False, "rows": [], "home_watts": 0.0,
                          "channels": {}, "home_channel": None, "ts": 0}
        self._listeners = []

        self._rules = self._load_json(_RULES_FILE, {})    # id -> rule dict
        self._state = self._load_json(_STATE_FILE, {})    # id -> {was_over, last_fired}

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
        }
        self._evaluate_rules(watts_by_name)
        self._notify()

    # ── Rule evaluation (rising/falling edge + cooldown) ──

    def _evaluate_rules(self, watts_by_name):
        now = time.time()
        with self._rules_lock:
            rules = list(self._rules.values())
        changed = False
        for rule in rules:
            rid = rule.get("id")
            dev = str(rule.get("device", "")).strip().lower()
            try:
                limit = float(rule.get("limit", 0))
                cooldown = float(rule.get("cooldown", 300))
            except (TypeError, ValueError):
                continue
            direction = str(rule.get("direction", "above")).lower()
            if dev not in watts_by_name:
                PIHOME_LOGGER.warn(f"Emporia alert '{rid}': device '{rule.get('device')}' not found this poll")
                continue

            watts = watts_by_name[dev]
            now_over = watts >= limit
            st = self._state.get(rid) or {"was_over": now_over, "last_fired": 0}
            was_over = st.get("was_over", now_over)

            crossed = (direction == "above" and not was_over and now_over) or \
                      (direction == "below" and was_over and not now_over)
            if crossed and (now - st.get("last_fired", 0) >= cooldown):
                self._fire(rule, watts)
                st["last_fired"] = now

            st["was_over"] = now_over
            self._state[rid] = st
            changed = True
        if changed:
            self._save_json(_STATE_FILE, self._state)

    def _fire(self, rule, watts):
        event = rule.get("event")
        if not isinstance(event, dict):
            PIHOME_LOGGER.error(f"Emporia alert '{rule.get('id')}': no valid 'event' dict to fire")
            return
        PIHOME_LOGGER.info(
            f"Emporia alert '{rule.get('id')}' fired: {rule.get('device')} "
            f"{rule.get('direction')} {rule.get('limit')}W (now {watts:.0f}W)"
        )

        def _do(dt):
            try:
                # Imported lazily to avoid a circular import at module load.
                from events.pihomeevent import PihomeEventFactory
                PihomeEventFactory.create_event_from_dict(dict(event)).execute()
            except Exception as e:
                PIHOME_LOGGER.error(f"Emporia alert '{rule.get('id')}': action failed: {e}")

        Clock.schedule_once(_do, 0)  # actions often touch the UI — run on main thread

    # ── Public rule API (called by the rule-management events) ──

    def add_or_update_rule(self, rule):
        rid = str(rule.get("id") or "").strip()
        if not rid:
            return self._err("'id' is required")
        if not rule.get("device"):
            return self._err("'device' is required")
        if rule.get("limit") is None:
            return self._err("'limit' (watts) is required")
        if not isinstance(rule.get("event"), dict):
            return self._err("'event' must be a nested event object")
        direction = str(rule.get("direction", "above")).lower()
        if direction not in ("above", "below"):
            return self._err("'direction' must be 'above' or 'below'")
        try:
            limit = float(rule["limit"])
            cooldown = float(rule.get("cooldown", 300))
        except (TypeError, ValueError):
            return self._err("'limit' and 'cooldown' must be numbers")

        stored = {"id": rid, "device": str(rule["device"]), "limit": limit,
                  "direction": direction, "cooldown": cooldown, "event": rule["event"]}
        with self._rules_lock:
            self._rules[rid] = stored
            self._save_json(_RULES_FILE, self._rules)
            # Reset latch so a stale state can't suppress or spuriously fire the new rule.
            self._state.pop(rid, None)
            self._save_json(_STATE_FILE, self._state)
        return {"code": 200, "body": {"status": "success",
                "message": f"Emporia alert '{rid}' saved", "rule": stored}}

    def remove_rule(self, rid):
        rid = str(rid or "").strip()
        with self._rules_lock:
            existed = self._rules.pop(rid, None) is not None
            self._state.pop(rid, None)
            self._save_json(_RULES_FILE, self._rules)
            self._save_json(_STATE_FILE, self._state)
        msg = f"Emporia alert '{rid}' removed" if existed else f"Emporia alert '{rid}' not found"
        return {"code": 200, "body": {"status": "success", "message": msg}}

    def list_rules(self):
        with self._rules_lock:
            rules = list(self._rules.values())
        return {"code": 200, "body": {"status": "success", "rules": rules}}

    @staticmethod
    def _err(message):
        return {"code": 400, "body": {"status": "error", "message": message}}

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
        """Blocking — call from a background thread. Returns (vals, labels) or (None, None)."""
        if self._vue is None or Scale is None or channel is None:
            return None, None
        try:
            now = datetime.now(timezone.utc)
            with self._vue_lock:
                usage, start = self._vue.get_chart_usage(
                    channel, start=now - timedelta(days=days), end=now,
                    scale=Scale.DAY.value, unit=Unit.KWH.value,
                )
            vals = [float(v) if v is not None else 0.0 for v in (usage or [])]
            base = start or (now - timedelta(days=days))
            labels = [(base + timedelta(days=i)).strftime("%m/%d") for i in range(len(vals))]
            return vals, labels
        except Exception as e:
            PIHOME_LOGGER.error(f"Emporia: chart fetch failed: {e}")
            return None, None


EMPORIA_SERVICE = EmporiaService()
