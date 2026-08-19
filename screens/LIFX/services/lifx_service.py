"""Always-on LIFX service: discovery, state, and the write path.

Loaded at boot from the manifest's ``services`` array by
``util/screen_services.py``, so the ``lifx`` event works whether or not the
screen has ever been opened.  Import it by package path -
``from screens.LIFX.services.lifx_service import LIFX_SERVICE`` - so everyone
shares the one singleton.

Threads
-------
``lifx-rx``     owned by the transport; the only caller of ``recvfrom``
``lifx-disco``  config watch, discovery sweeps, cloud scene sync, cache writes
``lifx-cmd``    drains the coalescing queue; the only writer for UI drags
``lifx-poll``   refreshes bulb state, and only while the screen is open

Poll versus user
----------------
A poll can land *before* a bulb has applied the SetColor we just sent, which
would snap a slider back under the user's finger.  Every write therefore
stamps the registry with the requested value and a short expiry
(``_optimistic``); a poll result is merged only for fields that aren't still
under an unexpired stamp.  Resolving it here rather than per-widget means the
same bulb shown in a room row and in the control panel can never disagree.
"""

import copy
import json
import os
import threading
import time
from collections import OrderedDict

from kivy.clock import Clock

from screens.LIFX import client as lifx_client
from screens.LIFX import protocol as p
from screens.LIFX import targeting
from screens.LIFX.scenes import LifxCloud, SceneStore, resolve_scene_states
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

DEVICES_FILE = "cache/lifx_devices.json"

_MIN_SEND_INTERVAL = 0.10    # per bulb; LIFX firmware degrades above ~20 msg/s
_OPTIMISTIC_WINDOW = 2.5     # seconds a requested value outranks a poll
_OFFLINE_AFTER = 3           # missed sweeps before a bulb is marked offline
_SUPERVISOR_TICK = 10.0


def _as_bool(value, default="0"):
    return str(CONFIG.get("lifx", value, default)).strip().lower() in ("1", "true")


class LifxService(object):

    def __init__(self):
        self._stop = threading.Event()
        self._wake = threading.Event()          # interrupts the supervisor sleep
        self._fast_poll = threading.Event()     # set while the screen is open

        self._registry_lock = threading.RLock()
        self._registry = {}
        self._optimistic = {}                   # serial -> (expires_at, {field: value})
        self._missed = {}                       # serial -> consecutive missed sweeps

        self._listeners = []
        self._listener_lock = threading.Lock()

        self._pending = OrderedDict()
        self._pending_cv = threading.Condition()
        self._last_send = {}

        self._transport = None
        self._transport_lock = threading.RLock()

        self._scenes = SceneStore()
        self._cloud = None
        self._last_discovery = 0.0
        self._last_cloud_sync = 0.0
        self._scanning = False
        self._error = None
        self._force_discovery = False

        self._read_config()
        self._load_cache()

        for target, name in ((self._run_supervisor, "lifx-disco"),
                             (self._run_commands, "lifx-cmd"),
                             (self._run_poll, "lifx-poll")):
            threading.Thread(target=target, daemon=True, name=name).start()

    # ── Configuration ─────────────────────────────────────────────────────

    def _read_config(self):
        """-> True when something connection-relevant changed."""
        previous = (getattr(self, "enabled", None),
                    getattr(self, "broadcast_address", None),
                    getattr(self, "room_source", None))

        self.enabled = _as_bool("enabled", "1")
        self.discovery_interval = max(1, CONFIG.get_int(
            "lifx", "discovery_interval", 5)) * 60.0
        self.refresh_interval = max(2, CONFIG.get_int("lifx", "refresh_interval", 5))
        self.transition_ms = max(0, CONFIG.get_int("lifx", "transition_ms", 400))
        self.cloud_token = CONFIG.get("lifx", "cloud_token", "").strip()
        self.cloud_sync_interval = max(0, CONFIG.get_int(
            "lifx", "cloud_sync_interval", 60)) * 60.0
        self.broadcast_address = CONFIG.get("lifx", "broadcast_address", "").strip()
        self.timeout = max(0.1, CONFIG.get_int("lifx", "timeout_ms", 600) / 1000.0)
        self.room_source = CONFIG.get("lifx", "room_source", "Group").strip()

        self._cloud = LifxCloud(self.cloud_token) if self.cloud_token else None
        return previous != (self.enabled, self.broadcast_address, self.room_source)

    def reload(self):
        changed = self._read_config()
        if not self.enabled:
            self._close_transport()
        elif changed:
            self._close_transport()             # rebind with the new settings
            with self._registry_lock:
                for entry in self._registry.values():
                    self._apply_room_source(entry)
            self._force_discovery = True
        self._wake.set()
        self._notify()

    def _apply_room_source(self, entry):
        """Rooms come from the LIFX app's groups, unless the user picked Location."""
        if self.room_source.lower().startswith("loc"):
            entry["group"] = entry.get("location") or ""
            entry["group_id"] = entry.get("location_id") or ""
        else:
            entry["group"] = entry.get("group_raw") or ""
            entry["group_id"] = entry.get("group_id_raw") or ""

    # ── Cache ─────────────────────────────────────────────────────────────

    def _load_cache(self):
        """Seed the registry from disk so the screen paints before any network."""
        try:
            with open(DEVICES_FILE, "r") as handle:
                raw = json.load(handle)
        except (FileNotFoundError, ValueError, OSError):
            return
        if not isinstance(raw, dict):
            return
        with self._registry_lock:
            for serial, entry in raw.items():
                if not isinstance(entry, dict):
                    continue
                entry["online"] = False        # unproven until a sweep says so
                entry.setdefault("group_raw", entry.get("group", ""))
                entry.setdefault("group_id_raw", entry.get("group_id", ""))
                self._apply_room_source(entry)
                self._registry[serial] = entry

    def _save_cache(self):
        try:
            directory = os.path.dirname(DEVICES_FILE)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with self._registry_lock:
                snapshot = copy.deepcopy(self._registry)
            with open(DEVICES_FILE, "w") as handle:
                json.dump(snapshot, handle, indent=2, sort_keys=True)
        except OSError as exc:
            PIHOME_LOGGER.error("LIFX: could not write device cache: {}".format(exc))

    # ── Transport ─────────────────────────────────────────────────────────

    def _get_transport(self):
        with self._transport_lock:
            if self._transport is None and self.enabled and not self._stop.is_set():
                transport = lifx_client.LifxTransport()
                transport.start()
                self._transport = transport
                PIHOME_LOGGER.info(
                    "LIFX: transport listening on port {}".format(transport.port))
            return self._transport

    def _close_transport(self):
        with self._transport_lock:
            transport, self._transport = self._transport, None
        if transport is not None:
            transport.close()

    def _device(self, serial, entry=None):
        entry = entry or self._registry.get(serial)
        if not entry or not entry.get("ip"):
            return None
        return lifx_client.Device(serial, entry["ip"],
                                  entry.get("port") or p.LIFX_PORT)

    # ── Supervisor: discovery and cloud sync ──────────────────────────────

    def _run_supervisor(self):
        self._wake.wait(2.0)                    # let the app finish booting
        while not self._stop.is_set():
            try:
                self._supervise_once()
            except Exception as exc:            # never let this thread die
                PIHOME_LOGGER.error("LIFX: discovery loop error: {}".format(exc))
                self._error = str(exc)
            self._wake.wait(_SUPERVISOR_TICK)
            self._wake.clear()

    def _supervise_once(self):
        self._read_config()
        if not self.enabled:
            self._close_transport()
            return

        now = time.time()
        due = (self._force_discovery
               or now - self._last_discovery >= self.discovery_interval)
        if due:
            self._force_discovery = False
            self.sweep()

        if self._cloud is not None and self._cloud.available:
            cloud_due = (self._last_cloud_sync == 0.0
                         or (self.cloud_sync_interval
                             and now - self._last_cloud_sync
                             >= self.cloud_sync_interval))
            if cloud_due:
                self.sync_cloud_scenes()

    def sweep(self):
        """One discovery pass: find bulbs, refresh their metadata, age out the rest."""
        transport = self._get_transport()
        if transport is None:
            return {}

        self._scanning = True
        self._notify()
        try:
            addresses = lifx_client.broadcast_addresses(self.broadcast_address)
            found = lifx_client.discover(transport, rounds=3, per_round=1.0,
                                         addresses=addresses)
            for serial, device in found.items():
                try:
                    entry = lifx_client.fetch_metadata(transport, device,
                                                       timeout=self.timeout)
                except lifx_client.LifxTimeout:
                    continue
                entry["group_raw"] = entry.get("group", "")
                entry["group_id_raw"] = entry.get("group_id", "")
                self._apply_room_source(entry)
                with self._registry_lock:
                    self._registry[serial] = entry
                    self._missed[serial] = 0

            with self._registry_lock:
                for serial, entry in self._registry.items():
                    if serial in found:
                        continue
                    missed = self._missed.get(serial, 0) + 1
                    self._missed[serial] = missed
                    if missed >= _OFFLINE_AFTER:
                        entry["online"] = False

            self._last_discovery = time.time()
            self._error = None
            self._save_cache()
            PIHOME_LOGGER.info("LIFX: discovery found {} bulb(s)".format(len(found)))
            return found
        finally:
            self._scanning = False
            self._notify()

    def sync_cloud_scenes(self):
        """Import LIFX app scenes.  They are then applied over the LAN, not the cloud."""
        if self._cloud is None or not self._cloud.available:
            return 0
        try:
            imported = self._scenes.merge_cloud(self._cloud.list_scenes())
            self._last_cloud_sync = time.time()
            PIHOME_LOGGER.info(
                "LIFX: imported {} cloud scene(s)".format(imported))
            self._notify()
            return imported
        except Exception as exc:
            self._last_cloud_sync = time.time()   # don't hammer a bad token
            PIHOME_LOGGER.error("LIFX: cloud scene sync failed: {}".format(exc))
            self._error = "Cloud scenes: {}".format(exc)
            return 0

    def discover_now(self, blocking=False, timeout=8.0):
        if not self.enabled:
            return {"code": 503, "body": {"status": "error",
                                          "message": "LIFX is disabled in Settings"}}
        if blocking:
            found = self.sweep()
            return {"code": 200, "body": {"status": "success",
                                          "message": "Found {} bulb(s)".format(len(found)),
                                          "count": len(found)}}
        self._force_discovery = True
        self._wake.set()
        return {"code": 200, "body": {"status": "success",
                                      "message": "LIFX discovery started"}}

    # ── Poll loop ─────────────────────────────────────────────────────────

    def _run_poll(self):
        while not self._stop.is_set():
            if not self._fast_poll.wait(1.0):
                continue                        # screen closed: nothing to refresh
            if self._stop.is_set():
                return
            try:
                self._poll_once()
            except Exception as exc:
                PIHOME_LOGGER.error("LIFX: poll error: {}".format(exc))
            self._stop.wait(self.refresh_interval)

    def _poll_once(self):
        transport = self._get_transport()
        if transport is None:
            return
        with self._registry_lock:
            targets = [(s, dict(e)) for s, e in self._registry.items()
                       if e.get("online", True) and e.get("ip")]
        if not targets:
            return

        changed = False
        for serial, entry in targets:
            if self._stop.is_set():
                return
            device = self._device(serial, entry)
            if device is None:
                continue
            try:
                state = lifx_client.get_light_state(transport, device,
                                                    timeout=self.timeout, retries=1)
            except lifx_client.LifxTimeout:
                continue
            polled = {
                "hue": state["hue"], "saturation": state["saturation"],
                "brightness": state["brightness"], "kelvin": state["kelvin"],
                "power": state["power"], "label": state["label"],
                "seen_at": time.time(), "online": True,
            }
            if self._merge_poll(serial, polled):
                changed = True

        if changed:
            self._notify()

    def _merge_poll(self, serial, polled):
        """Apply a poll result, letting unexpired optimistic values win."""
        with self._registry_lock:
            entry = self._registry.get(serial)
            if entry is None:
                return False
            expires, fields = self._optimistic.get(serial, (0.0, {}))
            if time.monotonic() < expires:
                polled = {k: v for k, v in polled.items() if k not in fields}
            elif serial in self._optimistic:
                self._optimistic.pop(serial, None)
            changed = any(entry.get(k) != v for k, v in polled.items()
                          if k not in ("seen_at",))
            entry.update(polled)
            return changed

    def _mark_optimistic(self, serials, fields, seconds=_OPTIMISTIC_WINDOW):
        deadline = time.monotonic() + seconds
        with self._registry_lock:
            for serial in serials:
                entry = self._registry.get(serial)
                if entry is None:
                    continue
                _old_deadline, old = self._optimistic.get(serial, (0.0, {}))
                merged = dict(old)
                merged.update(fields)
                self._optimistic[serial] = (deadline, merged)
                entry.update(fields)

    # ── Command queue ─────────────────────────────────────────────────────

    def _enqueue(self, key, job):
        """Replace any queued job with the same key, so a drag collapses to its newest value."""
        with self._pending_cv:
            self._pending.pop(key, None)
            self._pending[key] = job
            self._pending_cv.notify()

    def _run_commands(self):
        while not self._stop.is_set():
            with self._pending_cv:
                while not self._pending and not self._stop.is_set():
                    self._pending_cv.wait(1.0)
                if self._stop.is_set():
                    return
                _key, job = self._pending.popitem(last=False)
            try:
                self._dispatch(job)
            except Exception as exc:
                PIHOME_LOGGER.error("LIFX: command failed: {}".format(exc))

    def _dispatch(self, job):
        transport = self._get_transport()
        if transport is None:
            return
        final = job.get("final", True)
        for serial in job["serials"]:
            if self._stop.is_set():
                return
            with self._registry_lock:
                entry = self._registry.get(serial)
                entry = dict(entry) if entry else None
            device = self._device(serial, entry)
            if device is None:
                continue

            wait = self._throttle_wait(serial)
            if wait > 0:
                if not final:
                    continue                    # a newer frame is moments away
                self._stop.wait(wait)           # the last value must land
            self._last_send[serial] = time.monotonic()

            self._send(transport, device, job, wait_ack=final,
                       retries=2 if final else 0)

    def _throttle_wait(self, serial):
        last = self._last_send.get(serial)
        if last is None:
            return 0.0
        return max(0.0, _MIN_SEND_INTERVAL - (time.monotonic() - last))

    def _send(self, transport, device, job, wait_ack=True, retries=2):
        duration = job.get("duration_ms", self.transition_ms)
        if job["type"] == "power":
            return lifx_client.set_power(transport, device, job["on"], duration,
                                         wait_ack=wait_ack, retries=retries)
        return lifx_client.set_color(transport, device, job["hsbk"], duration,
                                     wait_ack=wait_ack, retries=retries)

    @staticmethod
    def _key(kind, serials):
        return "{}:{}".format(kind, ",".join(sorted(serials)))

    # ── Non-blocking write API (the UI) ───────────────────────────────────

    def set_power(self, serials, on, duration_ms=None, final=True):
        serials = list(serials)
        if not serials:
            return
        self._mark_optimistic(serials, {"power": bool(on)})
        self._enqueue(self._key("power", serials), {
            "type": "power", "serials": serials, "on": bool(on),
            "duration_ms": self.transition_ms if duration_ms is None else duration_ms,
            "final": final,
        })
        self._notify()

    def set_hsbk(self, serials, hsbk, duration_ms=None, final=True, kind="color"):
        serials = list(serials)
        if not serials:
            return
        hue, saturation, brightness, kelvin = hsbk
        self._mark_optimistic(serials, {
            "hue": hue, "saturation": saturation,
            "brightness": brightness, "kelvin": kelvin,
        })
        self._enqueue(self._key(kind, serials), {
            "type": "color", "serials": serials, "hsbk": tuple(hsbk),
            "duration_ms": self.transition_ms if duration_ms is None else duration_ms,
            "final": final,
        })
        self._notify()

    def set_color(self, serials, hue, saturation, duration_ms=None, final=True):
        """Hue 0-360 and saturation 0-100, keeping each bulb's own brightness."""
        serials = list(serials)
        for serial in serials:
            entry = self.get_bulb(serial)
            if entry is None:
                continue
            brightness = entry.get("brightness", p.U16) / float(p.U16) * 100.0
            hsbk = p.hsbk_from_pct(hue, saturation, brightness,
                                   entry.get("kelvin", 3500))
            self.set_hsbk([serial], hsbk, duration_ms, final=final, kind="color")

    def set_brightness(self, serials, pct, duration_ms=None, final=True):
        for serial in list(serials):
            entry = self.get_bulb(serial)
            if entry is None:
                continue
            hue, saturation, _bri, kelvin = p.hsbk_to_pct(
                entry.get("hue", 0), entry.get("saturation", 0),
                entry.get("brightness", 0), entry.get("kelvin", 3500))
            hsbk = p.hsbk_from_pct(hue, saturation, pct, kelvin)
            self.set_hsbk([serial], hsbk, duration_ms, final=final, kind="bri")

    def set_kelvin(self, serials, kelvin, duration_ms=None, final=True):
        """White mode: zero the saturation so the temperature is actually visible."""
        for serial in list(serials):
            entry = self.get_bulb(serial)
            if entry is None:
                continue
            low, high = entry.get("kelvin_range") or (p.KELVIN_MIN, p.KELVIN_MAX)
            clamped = p.clamp_kelvin(kelvin, low, high)
            brightness = entry.get("brightness", p.U16) / float(p.U16) * 100.0
            hsbk = p.hsbk_from_pct(0, 0, brightness, clamped)
            self.set_hsbk([serial], hsbk, duration_ms, final=final, kind="bri")

    # ── Blocking write API (events, which need a result) ──────────────────

    def apply(self, serials, power=None, hsbk=None, duration_ms=None):
        """Set colour and/or power and wait for acks.  -> {"ok", "succeeded", "failed"}

        Colour is sent *before* power so switching a bulb on doesn't flash the
        previous colour first.
        """
        serials = list(serials)
        transport = self._get_transport()
        if transport is None:
            return {"ok": False, "succeeded": [], "failed": serials,
                    "error": "LIFX is disabled or the transport is down"}

        duration = self.transition_ms if duration_ms is None else duration_ms
        succeeded, failed = [], []

        for serial in serials:
            entry = self.get_bulb(serial)
            device = self._device(serial, entry)
            if device is None:
                failed.append(serial)
                continue

            wait = self._throttle_wait(serial)
            if wait > 0:
                self._stop.wait(wait)
            self._last_send[serial] = time.monotonic()

            ok = True
            if hsbk is not None:
                ok = lifx_client.set_color(transport, device, hsbk, duration)
            if ok and power is not None:
                ok = lifx_client.set_power(transport, device, bool(power), duration)

            (succeeded if ok else failed).append(serial)

        fields = {}
        if hsbk is not None:
            fields.update({"hue": hsbk[0], "saturation": hsbk[1],
                           "brightness": hsbk[2], "kelvin": hsbk[3]})
        if power is not None:
            fields["power"] = bool(power)
        if fields and succeeded:
            self._mark_optimistic(succeeded, fields)
        self._notify()

        return {"ok": not failed, "succeeded": succeeded, "failed": failed,
                "error": None}

    def apply_scene(self, name_or_id, duration=None):
        """Replay a scene's stored states over the LAN.

        -> {"ok", "scene", "succeeded", "failed", "unresolved", "error"}
        """
        scene = self._scenes.get(name_or_id)
        if scene is None:
            return {"ok": False, "scene": None, "succeeded": [], "failed": [],
                    "unresolved": [], "error": "scene_not_found"}

        with self._registry_lock:
            registry = copy.deepcopy(self._registry)
        applies, unresolved = resolve_scene_states(scene, registry)

        if not applies:
            return {"ok": False, "scene": scene, "succeeded": [], "failed": [],
                    "unresolved": unresolved, "error": "no_matching_bulbs"}

        duration_ms = (self.transition_ms if duration is None
                       else int(float(duration) * 1000))
        succeeded, failed = [], []
        for serial, hsbk, power in applies:
            result = self.apply([serial], power=power, hsbk=hsbk,
                                duration_ms=duration_ms)
            succeeded.extend(result["succeeded"])
            failed.extend(result["failed"])

        return {"ok": not failed, "scene": scene, "succeeded": succeeded,
                "failed": failed, "unresolved": unresolved, "error": None}

    # ── Scenes ────────────────────────────────────────────────────────────

    def list_scenes(self):
        return self._scenes.list()

    def get_scene(self, name_or_id):
        return self._scenes.get(name_or_id)

    def save_scene(self, name, serials=None):
        with self._registry_lock:
            registry = copy.deepcopy(self._registry)
        scene = self._scenes.save_snapshot(name, registry, serials)
        self._notify()
        return scene

    def remove_scene(self, sid):
        removed = self._scenes.remove(sid)
        if removed:
            self._notify()
        return removed

    # ── Reads ─────────────────────────────────────────────────────────────

    def get_bulb(self, serial):
        with self._registry_lock:
            entry = self._registry.get(serial)
            return dict(entry) if entry else None

    def get_registry(self):
        with self._registry_lock:
            return copy.deepcopy(self._registry)

    def resolve(self, target, target_type="auto"):
        """-> (serials, kind, name).  Raises targeting.TargetError."""
        return targeting.resolve_target(self.get_registry(), target, target_type)

    def get_snapshot(self):
        registry = self.get_registry()
        return {
            "ready": bool(self._last_discovery) or bool(registry),
            "enabled": self.enabled,
            "scanning": self._scanning,
            "bulbs": registry,
            "rooms": targeting.group_index(registry),
            "scenes": self._scenes.list(),
            "last_discovery": self._last_discovery,
            "error": self._error,
        }

    # ── Listeners ─────────────────────────────────────────────────────────

    def add_listener(self, callback):
        with self._listener_lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback):
        with self._listener_lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def set_fast_poll(self, active):
        if active:
            self._fast_poll.set()
        else:
            self._fast_poll.clear()

    def _notify(self):
        with self._listener_lock:
            listeners = list(self._listeners)
        if not listeners:
            return
        snapshot = self.get_snapshot()
        for callback in listeners:
            Clock.schedule_once(
                lambda dt, cb=callback, s=snapshot: self._safe_call(cb, s), 0)

    @staticmethod
    def _safe_call(callback, snapshot):
        try:
            callback(snapshot)
        except Exception as exc:
            PIHOME_LOGGER.error("LIFX: listener error: {}".format(exc))

    # ── Shutdown ──────────────────────────────────────────────────────────

    def shutdown(self):
        self._stop.set()
        self._wake.set()
        self._fast_poll.set()                   # release the poll thread
        with self._pending_cv:
            self._pending_cv.notify_all()
        self._close_transport()
        self._save_cache()


LIFX_SERVICE = LifxService()
