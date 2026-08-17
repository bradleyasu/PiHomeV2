"""BambuLabScreen — BambuLab 3D printer monitor for PiHome.

Printer state comes from ``services/bambu_service.py``, an always-on singleton
that owns the MQTT connection and pushes snapshots here; this screen renders
them and owns the camera stream. Keeping MQTT out of the screen is what lets
state-alert rules (screens/BambuLab/events/) fire while another screen is open.

Local Network Protocols
------------------------
BambuLab printers expose two local APIs used by this screen:

  MQTT  port 8883 (TLS) — real-time status: temperatures, progress, layers,
                           ETA, filament, speed, and printer state.
                           Handled by the service, not here.
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
  Short press → force reconnect (MQTT + camera)
  Long press  → go back to previous screen
"""

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
    from ffpyplayer.player import MediaPlayer as _MediaPlayer
    _FF_AVAILABLE = True
except ImportError:
    _FF_AVAILABLE = False

from interface.pihomescreen import PiHomeScreen
from screens.BambuLab.bambustate import (
    ACCENT as _ACCENT, COLOR_ACCENT as _COLOR_ACCENT, COLOR_ERROR as _COLOR_ERROR,
    COLOR_IDLE as _COLOR_IDLE, COLOR_PAUSE as _COLOR_PAUSE,
    format_eta, format_finish, format_temp, resolve_state_color,
)
from screens.BambuLab.services.bambu_service import BAMBU_SERVICE
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/BambuLab/bambulab.kv")

# ── Constants ──────────────────────────────────────────────────────────────────

_RTSP_PORT = 322


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
        self._camera_thread = None
        self._camera_stop   = threading.Event()
        self._camera_player = None
        self._camera_tex    = None   # reused texture to avoid per-frame allocation
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

    _format_temp = staticmethod(format_temp)

    def on_print_progress(self, inst, val):
        self.progress_text = f"{int(val)}%"

    def on_print_speed(self, inst, val):
        self.speed_text = f"{int(val)}%"

    def on_eta_minutes(self, inst, val):
        self.eta_text = self._format_eta(val)
        self._update_finish_text(val)

    _format_eta = staticmethod(format_eta)

    def _update_finish_text(self, minutes):
        """Compute the estimated wall-clock finish time, e.g. 'Done 3:42 PM'."""
        self.finish_text = format_finish(minutes, self.gcode_state)

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
        # The service re-reads its own settings and reconnects if needed; the
        # screen only has to restart the camera it owns.
        BAMBU_SERVICE.reload()
        if self.is_open:
            creds_changed = (
                self._ip != old_ip
                or self._access_code != old_code
                or self._serial != old_serial
            )
            if creds_changed:
                self._stop_camera()
                Clock.schedule_once(lambda dt: self._start_camera_if_enabled(), 1.0)
        super().on_config_update(config)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_enter(self, *args):
        self._load_config()
        # Render whatever the always-on service already knows, then follow it.
        self._apply_snapshot(BAMBU_SERVICE.get_snapshot())
        BAMBU_SERVICE.add_listener(self._apply_snapshot)
        self._start_camera_if_enabled()
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        # Only the camera is screen-scoped — the MQTT service keeps running so
        # state alerts still fire while another screen is open.
        BAMBU_SERVICE.remove_listener(self._apply_snapshot)
        self._stop_camera()
        return super().on_pre_leave(*args)

    def _start_camera_if_enabled(self):
        if not self._enabled:
            return
        if not self._ip or not self._access_code or not self._serial:
            PIHOME_LOGGER.warn("BambuLab: missing connection settings (ip/access_code/serial)")
            return
        if self.camera_enabled:
            self._start_camera()
        else:
            self.camera_status = "Camera Disabled"

    # ── Snapshot rendering ─────────────────────────────────────────────────────

    def _apply_snapshot(self, snap):
        """Map the service's snapshot dict onto this screen's Kivy properties.

        Runs on the main thread (the service marshals via Clock). Property
        observers turn these into the formatted display strings the KV binds to.
        """
        try:
            self.connection_state = snap["connection_state"]
            self.connection_label = self._connection_label(snap)
            self.status_color = self._connection_color(snap["connection_state"])

            self.gcode_state = snap["gcode_state"]
            self.state_label = snap["state_label"]
            self.state_color = resolve_state_color(snap["gcode_state"])
            self.job_name = snap["job_name"]

            self.print_progress = snap["progress"]
            self.layer_current  = snap["layer_current"]
            self.layer_total    = snap["layer_total"]
            self.eta_minutes    = snap["eta_minutes"]

            self.temp_nozzle        = snap["nozzle"]
            self.temp_nozzle_target = snap["nozzle_target"]
            self.temp_bed           = snap["bed"]
            self.temp_bed_target    = snap["bed_target"]
            self.temp_chamber       = snap["chamber"]
            self.print_speed        = snap["speed"]

            self.filament_type = snap["filament_type"]
            color = snap["filament_color"]
            if color:
                self.filament_color = color
            self.filament_has_color = bool(color)

            self.has_alert   = snap["alert_active"]
            self.alert_text  = snap["alert_text"]
            self.alert_color = list(_COLOR_ERROR if snap["alert_severe"] else _COLOR_PAUSE)

            # gcode_state is set above, but finish_text also depends on it and is
            # only recomputed by the eta observer — refresh it explicitly.
            self._update_finish_text(self.eta_minutes)
        except Exception as e:
            PIHOME_LOGGER.error(f"BambuLab: error applying snapshot: {e}")

    def _connection_label(self, snap):
        """Explain *why* we are disconnected when the reason is a config problem.

        Kept to 12 characters or fewer — the header slot is a fixed dp(86) wide.
        """
        if snap["connection_state"] == "connected":
            return "CONNECTED"
        if not self._enabled:
            return "DISABLED"
        if not self._ip or not self._access_code or not self._serial:
            return "NO CONFIG"
        if not BAMBU_SERVICE.available:
            return "NO MQTT LIB"
        return snap["connection_label"]

    @staticmethod
    def _connection_color(state):
        if state == "connected":
            return _COLOR_ACCENT
        if state == "error":
            return _COLOR_ERROR
        return _COLOR_IDLE

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
        BAMBU_SERVICE.reconnect()
        self._stop_camera()
        Clock.schedule_once(lambda dt: self._start_camera_if_enabled(), 0.5)
        return True

    def on_rotary_long_pressed(self):
        """Go back to previous screen."""
        self.go_back()
        return True
