"""``lifx`` - control a bulb, a room, or activate a scene.

    {"type": "lifx", "target": "Kitchen", "power": "on", "brightness": 60,
     "on_complete": {"type": "toast", "message": "$target at $brightness%"},
     "on_error":    {"type": "toast", "message": "$error", "level": "error"}}

Validation and target resolution happen synchronously so an HTTP caller gets a
real 400/404/409/503 instead of a cheerful 200 followed by silence.  Only the
LAN traffic is pushed onto a worker thread - ``execute_safe`` marshals
``execute`` onto the Kivy main thread, and a synchronous round trip across a
dozen bulbs would stall the UI for seconds.
"""

from threading import Thread

from events.pihomeevent import PihomeEvent, PihomeEventFactory
from screens.LIFX import protocol as p
from screens.LIFX.targeting import TargetError
from util.phlog import PIHOME_LOGGER
from util.rulestore import substitute

try:
    from screens.LIFX.services.lifx_service import LIFX_SERVICE
except ImportError:      # screen disabled or removed: events still get discovered
    LIFX_SERVICE = None

_POWER_WORDS = ("on", "off", "toggle")


class LifxEvent(PihomeEvent):
    type = "lifx"

    def __init__(self, target=None, target_type=None, power=None, brightness=None,
                 hue=None, saturation=None, kelvin=None, color=None, scene=None,
                 duration=None, on_complete=None, on_error=None, **kwargs):
        super().__init__()
        self.target = target
        self.target_type = target_type or "auto"
        self.power = power
        self.brightness = brightness
        self.hue = hue
        self.saturation = saturation
        self.kelvin = kelvin
        self.color = color
        self.scene = scene
        self.duration = duration
        self.on_complete = on_complete
        self.on_error = on_error

        self._color_parsed = None

    # ── Entry point ───────────────────────────────────────────────────────

    def execute(self):
        if LIFX_SERVICE is None:
            return self._fail(503, "no_devices", "The LIFX screen is not installed")

        error = self._validate()
        if error is not None:
            return error

        if self.scene:
            scene = LIFX_SERVICE.get_scene(self.scene)
            if scene is None:
                return self._fail(404, "scene_not_found",
                                  "No LIFX scene named '{}'".format(self.scene))
            Thread(target=self._run_scene, args=(scene,), daemon=True,
                   name="lifx-event").start()
            return self._accepted(scene["name"], "scene", 0)

        try:
            serials, kind, name = LIFX_SERVICE.resolve(self.target, self.target_type)
        except TargetError as exc:
            return self._fail(exc.code, exc.error_code, exc.message,
                              candidates=exc.candidates)

        Thread(target=self._run, args=(serials, kind, name), daemon=True,
               name="lifx-event").start()
        return self._accepted(name, kind, len(serials))

    # ── Validation ────────────────────────────────────────────────────────

    def _validate(self):
        if self.power is not None:
            if str(self.power).strip().lower() not in _POWER_WORDS:
                return self._fail(400, "bad_request",
                                  "power must be one of: {}".format(
                                      ", ".join(_POWER_WORDS)))

        for field, low, high in (("brightness", 0, 100), ("hue", 0, 360),
                                 ("saturation", 0, 100), ("kelvin", 1500, 9000)):
            value = getattr(self, field)
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                return self._fail(400, "bad_request",
                                  "{} must be a number".format(field))
            if not low <= number <= high:
                return self._fail(400, "bad_request",
                                  "{} must be between {} and {}".format(
                                      field, low, high))

        if self.duration is not None:
            try:
                if float(self.duration) < 0:
                    raise ValueError
            except (TypeError, ValueError):
                return self._fail(400, "bad_request",
                                  "duration must be a positive number of seconds")

        if self.color is not None:
            self._color_parsed = p.parse_color_string(self.color)
            if self._color_parsed is None:
                return self._fail(
                    400, "bad_request",
                    "Could not read colour '{}'. Use #RRGGBB, a name like "
                    "'red', or '2700k'".format(self.color))

        if not self._has_action():
            return self._fail(400, "bad_request",
                              "Nothing to do: set power, brightness, a colour, "
                              "or a scene")
        return None

    def _has_action(self):
        return any(v is not None for v in (self.power, self.brightness, self.hue,
                                           self.saturation, self.kelvin,
                                           self.color, self.scene))

    # ── Worker ────────────────────────────────────────────────────────────

    def _run(self, serials, kind, name):
        try:
            power = self._resolve_power(serials)
            duration_ms = self._duration_ms()
            results = {"succeeded": [], "failed": []}

            if self._touches_colour():
                # Colour is per bulb: without an explicit value each keeps its
                # own, and kelvin is clamped to what that model supports.
                for serial in serials:
                    hsbk = self._hsbk_for(serial)
                    outcome = LIFX_SERVICE.apply([serial], power=power, hsbk=hsbk,
                                                 duration_ms=duration_ms)
                    results["succeeded"].extend(outcome["succeeded"])
                    results["failed"].extend(outcome["failed"])
            else:
                outcome = LIFX_SERVICE.apply(serials, power=power, hsbk=None,
                                             duration_ms=duration_ms)
                results = outcome

            self._finish(results, serials, kind, name)
        except Exception as exc:
            PIHOME_LOGGER.error("LIFX event failed: {}".format(exc))
            self._fire(self.on_error, self._error_values(
                "internal", str(exc), name, kind, serials))

    def _run_scene(self, scene):
        try:
            result = LIFX_SERVICE.apply_scene(scene["id"], self.duration)
            values = self._base_values(scene["name"], "scene",
                                       result["succeeded"])
            values["scene"] = scene["name"]

            if result["ok"]:
                self._fire(self.on_complete, values)
                return

            if result["error"] == "no_matching_bulbs":
                message = ("Scene '{}' refers to bulbs that are not on this "
                           "network".format(scene["name"]))
                code = "scene_unresolved"
            else:
                message = "{} of {} bulb(s) did not respond".format(
                    len(result["failed"]),
                    len(result["failed"]) + len(result["succeeded"]))
                code = "timeout"

            values.update({"error": message, "error_code": code,
                           "failed": ", ".join(result["failed"]),
                           "count": str(len(result["succeeded"]))})
            self._fire(self.on_error, values)
        except Exception as exc:
            PIHOME_LOGGER.error("LIFX scene event failed: {}".format(exc))
            self._fire(self.on_error, self._error_values(
                "internal", str(exc), scene.get("name", ""), "scene", []))

    def _finish(self, results, serials, kind, name):
        values = self._base_values(name, kind, results["succeeded"])

        if results["failed"]:
            # Partial success is still a failure for an automation - silently
            # half-applying a command is the worst outcome.
            values.update({
                "error": "{} of {} bulb(s) did not respond".format(
                    len(results["failed"]), len(serials)),
                "error_code": "timeout",
                "failed": ", ".join(results["failed"]),
            })
            self._fire(self.on_error, values)
            return

        self._fire(self.on_complete, values)

    # ── Value computation ─────────────────────────────────────────────────

    def _touches_colour(self):
        return any(v is not None for v in (self.brightness, self.hue,
                                           self.saturation, self.kelvin,
                                           self.color))

    def _duration_ms(self):
        if self.duration is None:
            return None
        return int(float(self.duration) * 1000)

    def _resolve_power(self, serials):
        """'toggle' is evaluated across the whole selection: any on -> all off."""
        if self.power is None:
            return None
        word = str(self.power).strip().lower()
        if word == "on":
            return True
        if word == "off":
            return False
        any_on = False
        for serial in serials:
            entry = LIFX_SERVICE.get_bulb(serial)
            if entry and entry.get("power"):
                any_on = True
                break
        return not any_on

    def _hsbk_for(self, serial):
        """Merge the requested values over this bulb's current state."""
        entry = LIFX_SERVICE.get_bulb(serial) or {}
        cur_h, cur_s, cur_b, cur_k = p.hsbk_to_pct(
            entry.get("hue", 0) or 0,
            entry.get("saturation", 0) or 0,
            entry.get("brightness", p.U16) or 0,
            entry.get("kelvin", 3500) or 3500,
        )

        parsed = self._color_parsed or {}
        # A colour string sets hue and saturation; brightness stays its own
        # field so "colour red" doesn't also change the level.
        hue = self.hue if self.hue is not None else parsed.get("hue", cur_h)
        saturation = (self.saturation if self.saturation is not None
                      else parsed.get("saturation", cur_s))
        brightness = self.brightness if self.brightness is not None else cur_b
        kelvin = (self.kelvin if self.kelvin is not None
                  else parsed.get("kelvin", cur_k))

        # Asking for a temperature and nothing else means white - leaving the
        # old saturation on would make the kelvin change invisible.
        if (self.kelvin is not None and self.saturation is None
                and self.hue is None and self.color is None):
            saturation = 0

        low, high = entry.get("kelvin_range") or (p.KELVIN_MIN, p.KELVIN_MAX)
        return p.hsbk_from_pct(hue, saturation, brightness,
                               p.clamp_kelvin(kelvin, low, high))

    # ── Placeholders and responses ────────────────────────────────────────

    def _base_values(self, name, kind, succeeded):
        labels = []
        for serial in succeeded:
            entry = LIFX_SERVICE.get_bulb(serial) if LIFX_SERVICE else None
            labels.append((entry or {}).get("label") or serial)

        values = {
            "target": name or (self.target or "all"),
            "target_type": kind,
            "room": name if kind in ("group", "all") else "",
            "count": str(len(succeeded)),
            "serials": ", ".join(succeeded),
            "labels": ", ".join(labels),
            "duration": str(self.duration if self.duration is not None else ""),
            "scene": self.scene or "",
        }
        for field in ("power", "brightness", "hue", "saturation", "kelvin"):
            value = getattr(self, field)
            values[field] = "" if value is None else str(value)
        if succeeded:
            entry = LIFX_SERVICE.get_bulb(succeeded[0]) or {}
            rgb = p.hsbk_to_rgb(entry.get("hue", 0), entry.get("saturation", 0),
                                entry.get("brightness", 0),
                                entry.get("kelvin", 3500))
            values["rgb"] = "#{:02x}{:02x}{:02x}".format(*rgb)
        else:
            values["rgb"] = ""
        return values

    def _error_values(self, error_code, message, name, kind, serials):
        values = self._base_values(name, kind, [])
        values.update({"error": message, "error_code": error_code,
                       "failed": ", ".join(serials), "candidates": ""})
        return values

    def _fire(self, event_dict, values):
        """Run a nested on_complete / on_error event."""
        if not event_dict:
            return
        try:
            # substitute() deep-copies, so a stored event dict reused across
            # firings is never mutated.
            payload = substitute(event_dict, values)
            response = PihomeEventFactory.create_event_from_dict(payload).execute_safe()
            PIHOME_LOGGER.info("LIFX follow-up event executed: {}".format(response))
        except Exception as exc:
            PIHOME_LOGGER.error("LIFX follow-up event failed: {}".format(exc))

    def _accepted(self, name, kind, count):
        return {"code": 200, "body": {
            "status": "success",
            "message": "LIFX command sent to {}".format(name),
            "target": name, "target_type": kind, "count": count,
        }}

    def _fail(self, code, error_code, message, candidates=None):
        values = self._error_values(error_code, message,
                                    self.target or "all", self.target_type, [])
        if candidates:
            values["candidates"] = ", ".join(candidates)
        # Fire on a worker: an automation still wants to hear about a bad
        # target even though the caller also gets the error code back.
        Thread(target=self._fire, args=(self.on_error, values), daemon=True,
               name="lifx-onerror").start()

        body = {"status": "error", "message": message, "error_code": error_code}
        if candidates:
            body["candidates"] = candidates
        return {"code": code, "body": body}

    # ── Definition ────────────────────────────────────────────────────────

    def to_definition(self):
        return {
            "type": self.type,
            "target": self.type_def(
                "string", False,
                "Bulb name, room name, serial (d073d5xxxxxx) or 'all'. An exact "
                "room name wins over a bulb of the same name - use target_type "
                "to force the other one."),
            "target_type": self.type_def(
                "string", False, "Disambiguate the target",
                ["auto", "bulb", "group", "all"]),
            "power": self.type_def(
                "string", False,
                "on, off, or toggle (toggle is evaluated across the whole "
                "selection: if any bulb is on, all go off)",
                list(_POWER_WORDS)),
            "brightness": self.type_def("integer", False, "0-100"),
            "hue": self.type_def("integer", False, "0-360 degrees"),
            "saturation": self.type_def(
                "integer", False, "0-100 (0 is white, which uses kelvin)"),
            "kelvin": self.type_def(
                "integer", False,
                "1500-9000, clamped to what the bulb supports. On its own it "
                "also sets saturation to 0 so the change is visible."),
            "color": self.type_def(
                "string", False,
                "#RRGGBB, a name like 'red' or 'warm', or '2700k'. Sets hue and "
                "saturation only - use brightness for the level."),
            "scene": self.type_def(
                "string", False,
                "Scene name or id. Overrides target and all colour fields."),
            "duration": self.type_def(
                "integer", False, "Fade time in seconds (default from Settings)"),
            "on_complete": self.type_def(
                "event", False,
                "Event fired once every bulb has acknowledged. Placeholders: "
                "$target $count $labels $brightness $rgb $scene"),
            "on_error": self.type_def(
                "event", False,
                "Event fired on failure, including partial success. "
                "Placeholders: $error $error_code $failed $target"),
        }
