"""BambuLabScreen — BambuLab 3D printer monitor for PiHome.

Local Network Protocols
------------------------
BambuLab printers expose two local APIs used by this screen:

  MQTT  port 8883 (TLS) — real-time status: temperatures, progress, layers,
                           ETA, filament, speed, and printer state.
  RTSPS port 322        — live H.264 camera stream (RTSP over TLS).

Required printer settings
  - Enable "LAN Only Liveview" (Settings → Network → LAN Only Liveview)
    Required for the camera feed on firmware 01.06+.

Required PiHome settings (set via Settings → BambuLab)
  - ip            : Printer's local IP address
  - access_code   : Found in printer Settings → WLAN → Access Code
  - serial        : Printer serial number (Settings or Bambu Studio)
  - camera_enabled: Toggle to connect to the RTSPS camera stream

Rotary Encoder
  Turn        → cycle the right-side stat panel focus (Job → Temps → Speed/Filament)
  Short press → force MQTT reconnect
  Long press  → go back to previous screen
"""

import datetime
import json
import ssl
import threading
import time

from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty, ColorProperty, NumericProperty,
    ObjectProperty, StringProperty,
)

try:
    import paho.mqtt.client as _mqtt_lib
    _MQTT_AVAILABLE = True
    _MQTT_V2 = hasattr(_mqtt_lib, 'CallbackAPIVersion')
except ImportError:
    _MQTT_AVAILABLE = False
    _MQTT_V2 = False

try:
    from ffpyplayer.player import MediaPlayer as _MediaPlayer
    _FF_AVAILABLE = True
except ImportError:
    _FF_AVAILABLE = False

from interface.pihomescreen import PiHomeScreen
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/BambuLab/bambulab.kv")

# ── Constants ──────────────────────────────────────────────────────────────────

_MQTT_PORT    = 8883
_RTSP_PORT    = 322
_MQTT_USER    = "bblp"
_REPORT_TOPIC  = "device/{serial}/report"
_REQUEST_TOPIC = "device/{serial}/request"

# Interval between periodic pushall requests (seconds).
# P1P has performance constraints — Bambu recommends no more than once per 5 min.
_PUSHALL_INTERVAL = 300

# BambuLab brand green
_ACCENT = (0.0, 0.68, 0.26, 1.0)

_STATE_LABELS = {
    "IDLE":    "IDLE",
    "RUNNING": "PRINTING",
    "PAUSE":   "PAUSED",
    "FINISH":  "COMPLETE",
    "FAILED":  "FAILED",
    "OFFLINE": "OFFLINE",
}

# Pre-allocated color lists — avoids creating new list objects on every MQTT message
_COLOR_ACCENT      = list(_ACCENT)
_COLOR_IDLE        = [0.45, 0.45, 0.45, 1]
_COLOR_PAUSE       = [0.95, 0.65, 0.10, 1]
_COLOR_FAILED      = [0.85, 0.25, 0.25, 1]
_COLOR_FINISH      = [0.20, 0.60, 0.95, 1]
_COLOR_ERROR       = [0.85, 0.25, 0.25, 1]

_STATE_COLORS = {
    "RUNNING": _COLOR_ACCENT,
    "PAUSE":   _COLOR_PAUSE,
    "FAILED":  _COLOR_FAILED,
    "FINISH":  _COLOR_FINISH,
}


# ── Screen ─────────────────────────────────────────────────────────────────────

class BambuLabScreen(PiHomeScreen):

    # Theme colors — standard names picked up automatically by on_config_update
    bg_color     = ColorProperty([0.04, 0.04, 0.06, 1])
    header_color = ColorProperty([0.07, 0.07, 0.10, 1])
    card_color   = ColorProperty([0.09, 0.09, 0.13, 1])
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([1, 1, 1, 0.45])
    accent_color = ColorProperty(list(_ACCENT))
    status_color = ColorProperty([0.45, 0.45, 0.45, 1])

    # Connection
    connection_state = StringProperty("disconnected")

    # Print job
    job_name       = StringProperty("No Active Print")
    gcode_state    = StringProperty("IDLE")
    state_label    = StringProperty("IDLE")
    state_color    = ColorProperty([0.45, 0.45, 0.45, 1])
    print_progress = NumericProperty(0)
    layer_current  = NumericProperty(0)
    layer_total    = NumericProperty(0)
    eta_minutes    = NumericProperty(0)

    # Temperatures (current + target)
    temp_nozzle         = NumericProperty(0.0)
    temp_bed            = NumericProperty(0.0)
    temp_chamber        = NumericProperty(0.0)
    temp_nozzle_target  = NumericProperty(0.0)
    temp_bed_target     = NumericProperty(0.0)

    # Speed & material
    # Default is -1 (not a real speed) so the first genuine value — often 100% —
    # differs from the default and reliably triggers on_print_speed.
    print_speed       = NumericProperty(-1)
    filament_type     = StringProperty("—")        # human-readable name (e.g. "PLA Matte")
    filament_color    = ColorProperty([0, 0, 0, 0])  # swatch color from active tray
    filament_has_color = BooleanProperty(False)      # whether a swatch should be shown

    # Camera
    camera_texture  = ObjectProperty(None, allownone=True)
    camera_status   = StringProperty("No Camera Feed")
    camera_enabled  = BooleanProperty(False)

    # Stat panel focus (0 = Job, 1 = Temperatures, 2 = Speed/Filament)
    stat_page = NumericProperty(0)

    # Formatted display strings — computed in Python to avoid f-strings in KV,
    # which are incompatible with Kivy's AST parser on Python 3.12+.
    nozzle_text      = StringProperty("—°C")
    bed_text         = StringProperty("—°C")
    chamber_text     = StringProperty("—°C")
    progress_text    = StringProperty("0%")
    layer_text       = StringProperty("—")
    eta_text         = StringProperty("—")
    finish_text      = StringProperty("")          # estimated wall-clock finish time
    speed_text       = StringProperty("—%")
    connection_label = StringProperty("DISCONNECTED")
    camera_label     = StringProperty("No Camera Feed")

    # Printer alerts (HMS health-management + print errors)
    has_alert   = BooleanProperty(False)
    alert_text  = StringProperty("")
    alert_color = ColorProperty([0.85, 0.25, 0.25, 1])

    # ──────────────────────────────────────────────────────────────────────────

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mqtt_client   = None
        self._mqtt_thread   = None
        self._mqtt_stop     = threading.Event()
        self._camera_thread = None
        self._camera_stop   = threading.Event()
        self._camera_player = None
        self._camera_tex    = None   # reused texture to avoid per-frame allocation
        self._device_serial = None   # auto-detected from MQTT topic
        self._load_config()

    # ── Property observers (keep formatted strings in sync) ────────────────────

    def on_temp_nozzle(self, inst, val):
        self._update_nozzle_text()

    def on_temp_nozzle_target(self, inst, val):
        self._update_nozzle_text()

    def on_temp_bed(self, inst, val):
        self._update_bed_text()

    def on_temp_bed_target(self, inst, val):
        self._update_bed_text()

    def on_temp_chamber(self, inst, val):
        self.chamber_text = f"{val:.1f}\u00b0C"

    def _update_nozzle_text(self):
        self.nozzle_text = self._format_temp(self.temp_nozzle, self.temp_nozzle_target)

    def _update_bed_text(self):
        self.bed_text = self._format_temp(self.temp_bed, self.temp_bed_target)

    @staticmethod
    def _format_temp(current, target) -> str:
        """Show 'current / target' when actively heating to a setpoint, else just current."""
        if target and target > 0:
            return f"{current:.0f}\u00b0 / {target:.0f}\u00b0C"
        return f"{current:.1f}\u00b0C"

    def on_print_progress(self, inst, val):
        self.progress_text = f"{int(val)}%"

    def on_print_speed(self, inst, val):
        self.speed_text = f"{int(val)}%"

    def on_eta_minutes(self, inst, val):
        self.eta_text = self._format_eta(val)
        self._update_finish_text(val)

    @staticmethod
    def _format_eta(minutes) -> str:
        """Format remaining minutes as 'ETA  Xh Ym' for long prints, 'ETA  N min' otherwise."""
        m = int(minutes)
        if m <= 0:
            return "\u2014"
        if m < 60:
            return f"ETA  {m} min"
        hours, mins = divmod(m, 60)
        if mins == 0:
            return f"ETA  {hours}h"
        return f"ETA  {hours}h {mins}m"

    def _update_finish_text(self, minutes):
        """Compute the estimated wall-clock finish time, e.g. 'Done 3:42 PM'."""
        m = int(minutes)
        if m <= 0 or self.gcode_state != "RUNNING":
            self.finish_text = ""
            return
        finish = datetime.datetime.now() + datetime.timedelta(minutes=m)
        # %-I strips the leading zero from the hour (Linux/macOS). Pi runs Linux.
        self.finish_text = "Done " + finish.strftime("%-I:%M %p")

    def on_layer_current(self, inst, val):
        self.layer_text = (
            f"{int(val)} / {self.layer_total}" if self.layer_total > 0 else "\u2014"
        )

    def on_layer_total(self, inst, val):
        self.layer_text = (
            f"{self.layer_current} / {int(val)}" if val > 0 else "\u2014"
        )

    def on_camera_status(self, inst, val):
        self.camera_label = val if val else "No Camera Feed"

    # ── Configuration ──────────────────────────────────────────────────────────

    def _load_config(self):
        def _bool(key, default="0"):
            return CONFIG.get("bambulab", key, default).strip().lower() in ("1", "true")

        self._ip          = CONFIG.get("bambulab", "ip",           "").strip()
        self._access_code = CONFIG.get("bambulab", "access_code",  "").strip()
        self._serial      = CONFIG.get("bambulab", "serial",       "").strip()
        self._enabled     = _bool("enabled")
        self.camera_enabled = _bool("camera_enabled")
        try:
            self._camera_fps = max(1, min(30, int(CONFIG.get("bambulab", "camera_fps", "5"))))
        except ValueError:
            self._camera_fps = 5

    def on_config_update(self, config):
        old_ip, old_code, old_serial = self._ip, self._access_code, self._serial
        self._load_config()
        if self.is_open:
            creds_changed = (
                self._ip != old_ip
                or self._access_code != old_code
                or self._serial != old_serial
            )
            if creds_changed:
                self._stop_mqtt()
                self._stop_camera()
                Clock.schedule_once(lambda dt: self._connect(), 1.0)
        super().on_config_update(config)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_enter(self, *args):
        self._load_config()
        self._connect()
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        self._stop_mqtt()
        self._stop_camera()
        return super().on_pre_leave(*args)

    def _connect(self):
        if not self._enabled:
            self._set_state("disconnected", "Disabled")
            return
        if not self._ip or not self._access_code or not self._serial:
            self._set_state("error", "Not Configured")
            PIHOME_LOGGER.warn("BambuLab: missing connection settings (ip/access_code/serial)")
            return
        self._start_mqtt()
        if self.camera_enabled:
            self._start_camera()
        else:
            self.camera_status = "Camera Disabled"

    # ── MQTT ───────────────────────────────────────────────────────────────────

    def _start_mqtt(self):
        if not _MQTT_AVAILABLE:
            PIHOME_LOGGER.error("BambuLab: paho-mqtt not installed — run: pip install paho-mqtt")
            self._set_state("error", "paho-mqtt missing")
            return
        if self._mqtt_thread and self._mqtt_thread.is_alive():
            return  # previous thread still shutting down, don't spawn a second
        self._mqtt_stop.clear()
        self._mqtt_thread = threading.Thread(target=self._mqtt_run, daemon=True, name="bambulab-mqtt")
        self._mqtt_thread.start()

    def _stop_mqtt(self):
        self._mqtt_stop.set()
        if self._mqtt_client:
            try:
                self._mqtt_client.disconnect()
            except Exception:
                pass
        self._mqtt_client = None

    def _mqtt_run(self):
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

            client.on_connect    = self._on_mqtt_connect
            client.on_disconnect = self._on_mqtt_disconnect
            client.on_message    = self._on_mqtt_message

            self._mqtt_client = client
            client.connect(self._ip, _MQTT_PORT, keepalive=60)

            last_pushall = time.monotonic()
            while not self._mqtt_stop.is_set():
                client.loop(timeout=1.0)
                # Periodically re-request full state (important for P1 series
                # which only sends changed fields in normal reports)
                now = time.monotonic()
                if now - last_pushall >= _PUSHALL_INTERVAL:
                    last_pushall = now
                    self._send_pushall(client)

        except Exception as e:
            PIHOME_LOGGER.error(f"BambuLab: MQTT thread error: {e}")
            Clock.schedule_once(lambda dt: self._set_state("error", "Connection Failed"), 0)

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
        PIHOME_LOGGER.info(f"BambuLab: sent pushall request to {serial}")

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if self._mqtt_stop.is_set():
            return
        if rc == 0:
            # Subscribe with single-level wildcard so we receive reports even
            # if the configured serial doesn't exactly match the printer's
            # device ID (the broker runs on the printer itself, so only that
            # printer's messages will arrive).
            client.subscribe("device/+/report")
            PIHOME_LOGGER.info("BambuLab: MQTT connected, subscribed to device/+/report")
            Clock.schedule_once(lambda dt: self._set_state("connected", "Connected"), 0)
            # Request full status snapshot so we get all fields immediately
            self._send_pushall(client)
        else:
            PIHOME_LOGGER.error(f"BambuLab: MQTT connect refused (rc={rc})")
            Clock.schedule_once(lambda dt: self._set_state("error", f"Auth Failed (rc={rc})"), 0)

    def _on_mqtt_disconnect(self, client, userdata, rc):
        if self._mqtt_stop.is_set():
            return
        PIHOME_LOGGER.warn(f"BambuLab: MQTT disconnected (rc={rc})")
        Clock.schedule_once(lambda dt: self._set_state("disconnected", "Disconnected"), 0)

    def _on_mqtt_message(self, client, userdata, msg):
        if self._mqtt_stop.is_set():
            return  # screen is inactive — discard
        try:
            payload = json.loads(msg.payload.decode())
        except Exception as e:
            PIHOME_LOGGER.error(f"BambuLab: MQTT JSON parse error: {e}")
            return

        # Auto-detect the real device serial from the topic so that pushall
        # requests target the correct device even if the config serial is wrong.
        # Topic format: device/<serial>/report
        parts = msg.topic.split("/")
        if len(parts) >= 2 and parts[0] == "device":
            detected = parts[1]
            if detected != self._device_serial:
                PIHOME_LOGGER.info(f"BambuLab: detected device serial {detected}")
                self._device_serial = detected

        p = payload.get("print")
        if p and isinstance(p, dict):
            Clock.schedule_once(lambda dt, data=p: self._apply_print_data(data), 0)

    def _set_state(self, state, label=""):
        self.connection_state = state
        self.connection_label = state.upper()
        if state == "connected":
            self.status_color = _COLOR_ACCENT
        elif state == "error":
            self.status_color = _COLOR_ERROR
        else:
            self.status_color = _COLOR_IDLE

    @staticmethod
    def _safe_int(value, fallback):
        """Convert value to int, returning fallback on None or error."""
        if value is None:
            return fallback
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _safe_float(value, fallback):
        """Convert value to float, returning fallback on None or error."""
        if value is None:
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _apply_print_data(self, p: dict):
        try:
            state = p.get("gcode_state")
            if state is not None:
                state_changed = state != self.gcode_state
                self.gcode_state = state
                self.state_label = _STATE_LABELS.get(state, state)
                self.state_color = self._resolve_state_color(state)
                # Finish time depends on whether we're RUNNING — refresh on change
                if state_changed:
                    self._update_finish_text(self.eta_minutes)

            self.print_progress = self._safe_int(p.get("mc_percent"), self.print_progress)
            self.layer_current  = self._safe_int(p.get("layer_num"), self.layer_current)
            self.layer_total    = self._safe_int(p.get("total_layer_num"), self.layer_total)
            self.eta_minutes    = self._safe_int(p.get("mc_remaining_time"), self.eta_minutes)
            self.temp_nozzle        = self._safe_float(p.get("nozzle_temper"), self.temp_nozzle)
            self.temp_bed           = self._safe_float(p.get("bed_temper"), self.temp_bed)
            self.temp_nozzle_target = self._safe_float(p.get("nozzle_target_temper"), self.temp_nozzle_target)
            self.temp_bed_target    = self._safe_float(p.get("bed_target_temper"), self.temp_bed_target)
            # chamber_temper was removed in recent firmware; fall back to
            # the nested device → ctc → info → temp path used by X1C.
            chamber = p.get("chamber_temper")
            if chamber is None:
                try:
                    chamber = p["device"]["ctc"]["info"]["temp"]
                except (KeyError, TypeError):
                    pass
            self.temp_chamber   = self._safe_float(chamber, self.temp_chamber)
            self.print_speed    = self._safe_int(p.get("spd_mag"), self.print_speed)

            job = p.get("subtask_name") or p.get("gcode_file")
            if job:
                self.job_name = job

            # Filament from the currently active tray
            ams_data = p.get("ams")
            if isinstance(ams_data, dict):
                self._apply_filament(ams_data, p.get("vt_tray"))

            # Health-management (HMS) alerts + print errors. Only update when the
            # printer included these keys in this report (P1 sends deltas).
            if "hms" in p or "print_error" in p:
                self._apply_alerts(p.get("hms"), p.get("print_error", 0))
        except Exception as e:
            PIHOME_LOGGER.error(f"BambuLab: error applying print data: {e}")

    def _apply_alerts(self, hms, print_error):
        """Surface printer health alerts as a banner.

        HMS entries are pairs of 32-bit ints (``attr``, ``code``). We format the
        canonical ``XXXX_XXXX_XXXX_XXXX`` code (lookup-able on the Bambu wiki) and
        derive a severity from the high word of ``code`` to color the banner.
        Exact human-readable text isn't in the payload, so we show the code.
        """
        severity_rank = {1: 3, 2: 2, 3: 1, 4: 0}  # fatal > serious > common > info
        codes = []
        worst = -1
        if isinstance(hms, list):
            for item in hms:
                if not isinstance(item, dict):
                    continue
                attr = self._safe_int(item.get("attr"), 0)
                code = self._safe_int(item.get("code"), 0)
                if attr == 0 and code == 0:
                    continue
                sev = (code >> 16) & 0xFFFF
                worst = max(worst, severity_rank.get(sev, 1))
                codes.append(
                    "{:04X}_{:04X}_{:04X}_{:04X}".format(
                        (attr >> 16) & 0xFFFF, attr & 0xFFFF,
                        (code >> 16) & 0xFFFF, code & 0xFFFF,
                    )
                )

        perr = self._safe_int(print_error, 0)

        if not codes and perr == 0:
            self.has_alert = False
            self.alert_text = ""
            return

        if perr != 0 and not codes:
            self.alert_text = f"Print Error  0x{perr:08X}"
            self.alert_color = list(_COLOR_ERROR)
        else:
            first = codes[0]
            extra = f"  (+{len(codes) - 1} more)" if len(codes) > 1 else ""
            self.alert_text = f"HMS  {first}{extra}"
            # Serious/fatal -> red, common/info -> amber
            self.alert_color = list(_COLOR_ERROR if worst >= 2 else _COLOR_PAUSE)
        self.has_alert = True

    def _apply_filament(self, ams_data: dict, vt_tray):
        """Resolve the active spool to a human-readable name and color swatch.

        The printer reports the loaded slot in ``tray_now`` (0-3 for AMS slots,
        254/255 for the external spool). We select that tray rather than the
        first non-empty one so the display matches what is actually printing.
        """
        tray_now = str(ams_data.get("tray_now", "255"))
        active = None

        if tray_now in ("254", "255"):
            # External (vt_tray) spool
            if isinstance(vt_tray, dict) and vt_tray.get("tray_type"):
                active = vt_tray
        else:
            for ams_unit in ams_data.get("ams", []):
                for tray in ams_unit.get("tray", []):
                    if str(tray.get("id")) == tray_now and tray.get("tray_type"):
                        active = tray
                        break
                if active:
                    break

        # Fallback: first loaded tray if the active slot couldn't be resolved
        if active is None:
            for ams_unit in ams_data.get("ams", []):
                for tray in ams_unit.get("tray", []):
                    if tray.get("tray_type"):
                        active = tray
                        break
                if active:
                    break

        if active is None:
            return

        # Prefer the descriptive sub-brand ("PLA Matte"), fall back to type ("PLA")
        name = (active.get("tray_sub_brands") or active.get("tray_type") or "").strip()
        if name:
            self.filament_type = name

        rgba = self._hex_to_rgba(active.get("tray_color", ""))
        if rgba:
            self.filament_color = rgba
            self.filament_has_color = True
        else:
            self.filament_has_color = False

    @staticmethod
    def _hex_to_rgba(hexstr: str):
        """Convert a Bambu 'RRGGBBAA' hex string to an opaque [r,g,b,1] list.

        Returns None for empty/transparent values (e.g. an unloaded slot) so the
        swatch can be hidden.
        """
        hexstr = (hexstr or "").strip()
        if len(hexstr) < 6:
            return None
        try:
            r = int(hexstr[0:2], 16) / 255.0
            g = int(hexstr[2:4], 16) / 255.0
            b = int(hexstr[4:6], 16) / 255.0
            a = int(hexstr[6:8], 16) / 255.0 if len(hexstr) >= 8 else 1.0
        except ValueError:
            return None
        if a == 0:
            return None  # fully transparent — treat as "no color"
        # Force opaque so the swatch is always visible regardless of source alpha
        return [r, g, b, 1.0]

    def _resolve_state_color(self, state: str) -> list:
        return _STATE_COLORS.get(state, _COLOR_IDLE)

    # ── Camera ─────────────────────────────────────────────────────────────────

    def _start_camera(self):
        if not _FF_AVAILABLE:
            PIHOME_LOGGER.error("BambuLab: ffpyplayer not available")
            self.camera_status = "ffpyplayer missing"
            return
        if self._camera_thread and self._camera_thread.is_alive():
            return  # previous thread still shutting down, don't spawn a second
        self.camera_status = "Connecting..."
        self._camera_stop.clear()
        self._camera_thread = threading.Thread(
            target=self._camera_run, daemon=True, name="bambulab-camera"
        )
        self._camera_thread.start()

    def _stop_camera(self):
        self._camera_stop.set()
        player = self._camera_player
        if player:
            try:
                player.close_player()
            except Exception:
                pass
        self._camera_player = None
        self._camera_tex    = None
        self.camera_texture = None

    def _camera_run(self):
        url = (
            f"rtsps://bblp:{self._access_code}@{self._ip}:{_RTSP_PORT}/streaming/live/1"
        )
        PIHOME_LOGGER.info(f"BambuLab: opening camera stream")
        try:
            player = _MediaPlayer(
                url,
                ff_opts={
                    "rtsp_transport": "tcp",
                    "an": True,   # no audio
                    "sn": False,
                    "fflags": "nobuffer",
                    "flags": "low_delay",
                    "framedrop": True,
                    "max_delay": "500000",
                },
                out_fmt="rgb24",
            )
            self._camera_player = player
            first_frame = True
            frame_interval = 1.0 / self._camera_fps
            last_upload = 0.0
            no_frame_count = 0

            while not self._camera_stop.is_set():
                frame, val = player.get_frame()
                if val == "eof" or self._camera_stop.is_set():
                    break
                if frame is not None:
                    no_frame_count = 0
                    now = time.monotonic()
                    if now - last_upload >= frame_interval:
                        last_upload = now
                        if first_frame:
                            first_frame = False
                            Clock.schedule_once(lambda dt: setattr(self, "camera_status", ""), 0)
                        img, _pts = frame
                        Clock.schedule_once(lambda dt, i=img: self._update_texture(i), 0)
                    # else: frame dropped — loop immediately to drain buffer
                else:
                    no_frame_count += 1
                    if no_frame_count > 150:  # ~15s at 10 checks/sec
                        PIHOME_LOGGER.warn("BambuLab: camera stream stalled, reconnecting")
                        Clock.schedule_once(lambda dt: setattr(self, "camera_status", "Reconnecting..."), 0)
                        break
                    self._camera_stop.wait(0.1)

        except Exception as e:
            PIHOME_LOGGER.error(f"BambuLab: camera error: {e}")
            Clock.schedule_once(lambda dt: setattr(self, "camera_status", "Stream Unavailable"), 0)
        finally:
            self._camera_player = None
            # Auto-reconnect if we broke out due to stall (not user-initiated stop)
            if not self._camera_stop.is_set() and self.camera_enabled:
                Clock.schedule_once(lambda dt: self._start_camera(), 3.0)

    def _update_texture(self, img):
        try:
            w, h = img.get_size()
            data = bytes(img.to_bytearray()[0])
            if self._camera_tex is None or self._camera_tex.size != (w, h):
                tex = Texture.create(size=(w, h), colorfmt="rgb")
                tex.flip_vertical()
                self._camera_tex = tex
            self._camera_tex.blit_buffer(data, colorfmt="rgb", bufferfmt="ubyte")
            self.camera_texture = self._camera_tex
            # blit_buffer updates pixels in-place on the same texture object,
            # so ObjectProperty won't detect a change and KV bindings won't
            # trigger a canvas redraw. Force-dispatch to repaint.
            self.property("camera_texture").dispatch(self)
        except Exception as e:
            PIHOME_LOGGER.error(f"BambuLab: texture update error: {e}")

    # ── Rotary encoder ─────────────────────────────────────────────────────────

    def on_rotary_turn(self, direction, button_pressed):
        """Cycle through stat panel focus pages."""
        self.stat_page = (self.stat_page + direction) % 3
        return True

    def on_rotary_pressed(self):
        """Force reconnect."""
        self._stop_mqtt()
        self._stop_camera()
        Clock.schedule_once(lambda dt: self._connect(), 0.5)
        return True

    def on_rotary_long_pressed(self):
        """Go back to previous screen."""
        self.go_back()
        return True
