"""Always-on BambuLab printer monitor.

Holds a single MQTT connection to the printer 24/7 (independent of which screen
is open), maintains a snapshot of printer state, and evaluates user-defined
state-alert rules. When the printer enters a state a rule is bound to — PRINTING,
COMPLETE, FAILED, an HMS/print error, or going on/offline — that rule's nested
PiHome event is fired.

Rules live in a shared :class:`~util.rulestore.RuleStore` (persistence, enable/
disable, cooldown, last-fired and firing), so this service only has to decide
*when* a trigger has occurred. They are managed via JSON events (see
screens/BambuLab/events/) over MQTT/HTTP/WebSocket, and appear on the Automations
screen. The BambuLab screen consumes this service's snapshot instead of running
its own MQTT client (one connection to the printer's on-board broker, and state
keeps flowing while you are on another screen — which is the whole point of the
rules).

Transitions are edge-triggered and the first report after each connect is a
baseline that never fires, so a network blip or a restart cannot replay a stale
completion. The tradeoff: a transition that happens entirely while PiHome is down
is missed.
"""

import json
import ssl
import threading
import time

from kivy.clock import Clock

from screens.BambuLab.bambustate import (
    TRIGGERS, new_snapshot, normalize_trigger, parse_print, placeholder_values,
    state_label, triggers_fired,
)
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER
from util.rulestore import RuleStore

try:
    import paho.mqtt.client as _mqtt_lib
    _MQTT_AVAILABLE = True
    _MQTT_V2 = hasattr(_mqtt_lib, "CallbackAPIVersion")
except ImportError:
    _MQTT_AVAILABLE = False
    _MQTT_V2 = False

_MQTT_PORT = 8883
_MQTT_USER = "bblp"
_REQUEST_TOPIC = "device/{serial}/request"

# Interval between periodic pushall requests (seconds).
# P1P has performance constraints — Bambu recommends no more than once per 5 min.
_PUSHALL_INTERVAL = 300

# Reconnect backoff bounds (seconds).
_RECONNECT_MIN = 5
_RECONNECT_MAX = 60

# How long the supervisor sleeps between config re-checks while idle/disabled.
_IDLE_POLL = 10

# How often a live session re-checks the printer settings for changes.
_CONFIG_POLL = 10


def _describe(rule):
    """Human-readable trigger text for the Automations screen."""
    trigger = rule.get("state", "?")
    return "Printer goes " + state_label(trigger)


# Rule storage, validation, cooldown and firing all live in the shared store —
# this service only decides *when* a trigger has occurred.
RULES = RuleStore(
    key="bambulab",
    label="BambuLab",
    path="cache/bambulab_state_rules.json",
    glyph="",          # print
    describe=_describe,
    create_event="bambulab_state_alert",
)


class BambuService:
    def __init__(self):
        self._stop = threading.Event()
        self._snapshot_lock = threading.Lock()

        self._mqtt_client = None
        self._device_serial = None      # auto-detected from the MQTT topic
        self._reconnect = threading.Event()   # set to force-drop the current session
        self._session_ok = False        # did the broker accept the current session?

        self._snapshot = new_snapshot()
        self._listeners = []

        self._ip = self._access_code = self._serial = ""
        self._enabled = False
        self._read_config()

        self._thread = threading.Thread(target=self._run, daemon=True, name="bambulab-service")
        self._thread.start()

    @property
    def available(self):
        return _MQTT_AVAILABLE

    # ── Config ──

    def _read_config(self):
        """Re-read settings. Returns True if the connection credentials changed."""
        ip = CONFIG.get("bambulab", "ip", "").strip()
        code = CONFIG.get("bambulab", "access_code", "").strip()
        serial = CONFIG.get("bambulab", "serial", "").strip()
        enabled = CONFIG.get("bambulab", "enabled", "0").strip().lower() in ("1", "true")

        changed = (ip, code, serial, enabled) != (
            self._ip, self._access_code, self._serial, self._enabled
        )
        self._ip, self._access_code, self._serial, self._enabled = ip, code, serial, enabled
        return changed

    def _configured(self):
        return bool(self._enabled and self._ip and self._access_code and self._serial)

    def reload(self):
        """Called by the screen's on_config_update — reconnect if creds changed."""
        if self._read_config():
            PIHOME_LOGGER.info("BambuLab service: settings changed, reconnecting")
            self.reconnect()

    def reconnect(self):
        """Drop the current MQTT session; the supervisor loop reconnects immediately."""
        self._reconnect.set()
        self._disconnect_client()

    # ── Supervisor loop ──

    def _run(self):
        if not _MQTT_AVAILABLE:
            PIHOME_LOGGER.error(
                "BambuLab service: paho-mqtt not installed — state alerts are inactive"
            )
            return

        backoff = _RECONNECT_MIN
        while not self._stop.is_set():
            self._read_config()
            if not self._configured():
                # Disabled or unconfigured: stay dark, but keep checking so the
                # service comes alive as soon as settings are filled in.
                self._set_connection(False, "disconnected")
                self._stop.wait(_IDLE_POLL)
                continue

            self._reconnect.clear()
            ok = self._mqtt_session()
            if self._stop.is_set():
                break
            # Only a session the broker actually accepted resets the backoff, so a
            # mid-print drop reconnects promptly while bad credentials (which fail
            # instantly, over and over) back off to one attempt a minute.
            backoff = _RECONNECT_MIN if ok else min(backoff * 2, _RECONNECT_MAX)
            self._stop.wait(backoff)

    def _mqtt_session(self):
        """Run one MQTT session to completion. Returns True if the broker accepted it."""
        self._session_ok = False
        try:
            if _MQTT_V2:
                client = _mqtt_lib.Client(
                    callback_api_version=_mqtt_lib.CallbackAPIVersion.VERSION1,
                    client_id="pihome_bambulab",
                )
            else:
                client = _mqtt_lib.Client(client_id="pihome_bambulab")

            client.username_pw_set(_MQTT_USER, self._access_code)

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            client.tls_set_context(ctx)

            client.on_connect = self._on_mqtt_connect
            client.on_disconnect = self._on_mqtt_disconnect
            client.on_message = self._on_mqtt_message

            self._mqtt_client = client
            client.connect(self._ip, _MQTT_PORT, keepalive=60)

            last_pushall = time.monotonic()
            last_cfg_check = time.monotonic()
            while not self._stop.is_set() and not self._reconnect.is_set():
                rc = client.loop(timeout=1.0)
                if rc != 0:
                    PIHOME_LOGGER.warn(f"BambuLab service: MQTT loop ended (rc={rc})")
                    break
                now = time.monotonic()
                # Periodically re-request full state (important for P1 series
                # which only sends changed fields in normal reports)
                if now - last_pushall >= _PUSHALL_INTERVAL:
                    last_pushall = now
                    self._send_pushall(client)
                # Poll our own settings too. The screen calls reload() on config
                # changes, but screens are instantiated lazily — if BambuLab has
                # never been opened, its on_config_update never runs and nothing
                # else would tell us the address changed.
                if now - last_cfg_check >= _CONFIG_POLL:
                    last_cfg_check = now
                    if self._read_config():
                        PIHOME_LOGGER.info(
                            "BambuLab service: settings changed, reconnecting"
                        )
                        break

        except Exception as e:
            PIHOME_LOGGER.error(f"BambuLab service: MQTT error: {e}")
        finally:
            self._disconnect_client()
            # Any new session starts from a clean baseline so the first report
            # after reconnecting cannot be mistaken for a transition.
            self._reset_baseline()
            # A session the broker never accepted is a real fault (unreachable,
            # wrong access code) — show it in red rather than plain disconnected.
            self._set_connection(False, "disconnected" if self._session_ok else "error")
        return self._session_ok

    def _disconnect_client(self):
        client = self._mqtt_client
        self._mqtt_client = None
        if client:
            try:
                client.disconnect()
            except Exception:
                pass

    def _send_pushall(self, client):
        """Ask the printer to push a full status snapshot."""
        serial = self._device_serial or self._serial
        topic = _REQUEST_TOPIC.format(serial=serial)
        payload = json.dumps({
            "pushing": {
                "sequence_id": "0",
                "command": "pushall",
                "version": 1,
                "push_target": 1,
            }
        })
        client.publish(topic, payload)
        PIHOME_LOGGER.info(f"BambuLab service: sent pushall request to {serial}")

    # ── MQTT callbacks ──

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._session_ok = True
            # Subscribe with a single-level wildcard so we receive reports even if
            # the configured serial doesn't exactly match the printer's device ID
            # (the broker runs on the printer itself, so only that printer's
            # messages will arrive).
            client.subscribe("device/+/report")
            PIHOME_LOGGER.info("BambuLab service: MQTT connected, subscribed to device/+/report")
            self._set_connection(True, "connected")
            self._send_pushall(client)
        else:
            PIHOME_LOGGER.error(f"BambuLab service: MQTT connect refused (rc={rc})")
            self._set_connection(False, "error")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        PIHOME_LOGGER.warn(f"BambuLab service: MQTT disconnected (rc={rc})")
        self._set_connection(False, "disconnected")

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception as e:
            PIHOME_LOGGER.error(f"BambuLab service: MQTT JSON parse error: {e}")
            return

        # Auto-detect the real device serial from the topic so that pushall
        # requests target the correct device even if the config serial is wrong.
        # Topic format: device/<serial>/report
        parts = msg.topic.split("/")
        if len(parts) >= 2 and parts[0] == "device":
            detected = parts[1]
            if detected != self._device_serial:
                PIHOME_LOGGER.info(f"BambuLab service: detected device serial {detected}")
                self._device_serial = detected

        p = payload.get("print")
        if isinstance(p, dict) and p:
            self._apply_report(p)

    # ── Snapshot maintenance ──

    def _apply_report(self, p):
        with self._snapshot_lock:
            prev = self._snapshot
            snap = parse_print(p, prev)
            self._snapshot = snap
        self._dispatch(prev, snap)
        self._notify()

    def _set_connection(self, connected, state):
        with self._snapshot_lock:
            prev = self._snapshot
            if prev["connected"] == connected and prev["connection_state"] == state:
                return
            snap = dict(prev)
            snap["connected"] = connected
            snap["connection_state"] = state
            snap["connection_label"] = state.upper()
            self._snapshot = snap
        self._dispatch(prev, snap)
        self._notify()

    def _reset_baseline(self):
        """Forget the seeded flag so the next report establishes a fresh baseline."""
        with self._snapshot_lock:
            if not self._snapshot.get("seeded"):
                return
            snap = dict(self._snapshot)
            snap["seeded"] = False
            self._snapshot = snap

    # ── Rule evaluation ──

    def _dispatch(self, prev, snap):
        for trigger in triggers_fired(prev, snap):
            self.fire_trigger(trigger, snap)

    def fire_trigger(self, trigger, snapshot=None):
        """Fire every rule bound to ``trigger``. Returns the number fired."""
        snap = snapshot if snapshot is not None else self.get_snapshot()
        return RULES.fire_matching("state", trigger, placeholder_values(snap))

    # ── Public rule API (called by the rule-management events) ──

    def add_or_update_rule(self, rule):
        """Validate the trigger, then hand persistence to the shared store."""
        state = normalize_trigger(rule.get("state"))
        if state is None:
            return {"code": 400, "body": {
                "status": "error",
                "message": f"'state' must be one of: {', '.join(TRIGGERS)}"}}
        return RULES.upsert(dict(rule, state=state))

    def remove_rule(self, rid):
        return RULES.remove(rid)

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
            PIHOME_LOGGER.error(f"BambuLab listener error: {e}")

    def shutdown(self):
        self._stop.set()
        self._disconnect_client()


BAMBU_SERVICE = BambuService()
