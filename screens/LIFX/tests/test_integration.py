"""End-to-end: LifxEvent -> service -> real UDP -> fake bulbs -> on_complete.

Needs Kivy, so run it with the app interpreter:

    venv/bin/python screens/LIFX/tests/test_integration.py

The service singleton starts its own background threads on import.  We stop
them immediately and drive the blocking write path directly, which keeps the
test fast and deterministic and stops it broadcasting onto the real network.
"""

import os
import sys
import threading
import time
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from screens.LIFX import client as c  # noqa: E402
from screens.LIFX import protocol as p  # noqa: E402
from screens.LIFX.tests.fakebulb import FakeBulb  # noqa: E402

import events.pihomeevent as pihomeevent  # noqa: E402
from screens.LIFX.events.lifxevent import LifxEvent  # noqa: E402
from screens.LIFX.events.lifxlistevent import LifxListEvent  # noqa: E402
from screens.LIFX.events.lifxsceneevents import (  # noqa: E402
    LifxSceneRemoveEvent,
    LifxSceneSaveEvent,
    LifxScenesEvent,
)
from screens.LIFX.services.lifx_service import LIFX_SERVICE  # noqa: E402


class _Recorder(object):
    """Stands in for the event factory so follow-ups don't need a running Clock."""

    def __init__(self):
        self.fired = []
        self._original = pihomeevent.PihomeEventFactory.create_event_from_dict

    def install(self):
        recorder = self

        def fake(event_dict):
            recorder.fired.append(event_dict)

            class _Stub(object):
                def execute_safe(self, timeout=10):
                    return {"code": 200, "body": {"status": "success"}}
            return _Stub()

        pihomeevent.PihomeEventFactory.create_event_from_dict = staticmethod(fake)
        # The event module imported the factory by name, so patch its reference too.
        import screens.LIFX.events.lifxevent as module
        self._module = module
        self._module_original = module.PihomeEventFactory
        module.PihomeEventFactory = pihomeevent.PihomeEventFactory

    def remove(self):
        pihomeevent.PihomeEventFactory.create_event_from_dict = self._original
        self._module.PihomeEventFactory = self._module_original

    def wait_for(self, count=1, timeout=6.0):
        deadline = time.monotonic() + timeout
        while len(self.fired) < count and time.monotonic() < deadline:
            time.sleep(0.02)
        return self.fired


class LifxStackCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Stop the background threads before they broadcast onto the real LAN.
        LIFX_SERVICE._stop.set()
        LIFX_SERVICE._wake.set()
        LIFX_SERVICE._fast_poll.set()
        LIFX_SERVICE.enabled = True
        LIFX_SERVICE.transition_ms = 0
        LIFX_SERVICE.timeout = 0.4

    def setUp(self):
        self.bulbs = []
        self.sink = self._bulb("d073d5000001", "Sink", "Kitchen")
        self.island = self._bulb("d073d5000002", "Island", "Kitchen")
        self.bed = self._bulb("d073d5000003", "Bed", "Bedroom")

        transport = c.LifxTransport(bind_addr="127.0.0.1")
        transport.start()
        LIFX_SERVICE._transport = transport
        self.transport = transport

        LIFX_SERVICE._registry = {b.serial: self._entry(b) for b in self.bulbs}
        LIFX_SERVICE._optimistic = {}
        LIFX_SERVICE._last_send = {}

        self.recorder = _Recorder()
        self.recorder.install()

    def tearDown(self):
        self.recorder.remove()
        self.transport.close()
        LIFX_SERVICE._transport = None
        for bulb in self.bulbs:
            bulb.stop()

    def _bulb(self, serial, label, group):
        bulb = FakeBulb(serial=serial, label=label, group=group).start()
        self.bulbs.append(bulb)
        return bulb

    @staticmethod
    def _entry(bulb):
        return {
            "serial": bulb.serial, "ip": "127.0.0.1", "port": bulb.port,
            "label": bulb.label, "group": bulb.group, "group_id": bulb.group.lower(),
            "group_raw": bulb.group, "group_id_raw": bulb.group.lower(),
            "location": "Home", "location_id": "home",
            "product": 27, "color": True, "kelvin_range": [1500, 9000],
            "hue": 0, "saturation": 0, "brightness": p.U16, "kelvin": 3500,
            "power": bulb.power, "seen_at": time.time(), "online": True,
        }


class TestLifxEventTargeting(LifxStackCase):

    def test_room_target_reaches_every_bulb_in_it(self):
        response = LifxEvent(target="Kitchen", power="off").execute()
        self.assertEqual(response["code"], 200)
        self.assertEqual(response["body"]["target_type"], "group")
        self.assertEqual(response["body"]["count"], 2)

        self.recorder.wait_for(0, timeout=0)
        self._settle()
        self.assertFalse(self.sink.power)
        self.assertFalse(self.island.power)
        self.assertTrue(self.bed.power, "the other room must be untouched")

    def test_single_bulb_target(self):
        response = LifxEvent(target="Island", power="off").execute()
        self.assertEqual(response["body"]["target_type"], "bulb")
        self._settle()
        self.assertFalse(self.island.power)
        self.assertTrue(self.sink.power)

    def test_all_target(self):
        LifxEvent(target="all", power="off").execute()
        self._settle()
        self.assertFalse(any(b.power for b in self.bulbs))

    def test_serial_target(self):
        LifxEvent(target="d073d5000003", power="off").execute()
        self._settle()
        self.assertFalse(self.bed.power)

    def test_toggle_is_evaluated_across_the_selection(self):
        """Any bulb on means the whole room goes off."""
        self.sink.power = True
        self.island.power = False
        LIFX_SERVICE._registry[self.sink.serial]["power"] = True
        LIFX_SERVICE._registry[self.island.serial]["power"] = False

        LifxEvent(target="Kitchen", power="toggle").execute()
        self._settle()
        self.assertFalse(self.sink.power)
        self.assertFalse(self.island.power)

    def test_unknown_target_returns_404_and_fires_on_error(self):
        response = LifxEvent(target="Garage", power="on",
                             on_error={"type": "toast",
                                       "message": "$error_code: $error"}).execute()
        self.assertEqual(response["code"], 404)
        self.assertEqual(response["body"]["error_code"], "bulb_not_found")

        fired = self.recorder.wait_for(1)
        self.assertEqual(len(fired), 1)
        self.assertIn("bulb_not_found", fired[0]["message"])

    def test_ambiguous_target_returns_409_with_candidates(self):
        response = LifxEvent(target="B", power="on").execute()
        self.assertEqual(response["code"], 409)
        self.assertEqual(response["body"]["error_code"], "ambiguous_target")
        self.assertIn("Bedroom", response["body"]["candidates"])

    def _settle(self, timeout=6.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not any(t.name == "lifx-event" for t in threading.enumerate()):
                return
            time.sleep(0.02)


class TestLifxEventColour(LifxStackCase):

    def _settle(self, timeout=6.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not any(t.name == "lifx-event" for t in threading.enumerate()):
                return
            time.sleep(0.02)

    def test_brightness_only_keeps_hue_and_saturation(self):
        self.sink.hue, self.sink.saturation = 30000, 40000
        LIFX_SERVICE._registry[self.sink.serial].update(
            {"hue": 30000, "saturation": 40000})

        LifxEvent(target="Sink", brightness=50).execute()
        self._settle()
        self.assertEqual(self.sink.hue, 30000)
        self.assertEqual(self.sink.saturation, 40000)
        self.assertAlmostEqual(self.sink.brightness / p.U16, 0.5, delta=0.01)

    def test_colour_string_sets_hue_and_saturation_not_brightness(self):
        LIFX_SERVICE._registry[self.sink.serial]["brightness"] = int(0.25 * p.U16)
        self.sink.brightness = int(0.25 * p.U16)

        LifxEvent(target="Sink", color="#00ff00").execute()
        self._settle()
        hue, sat, bri, _k = p.hsbk_to_pct(self.sink.hue, self.sink.saturation,
                                          self.sink.brightness, self.sink.kelvin)
        self.assertAlmostEqual(hue, 120.0, delta=1.0)
        self.assertAlmostEqual(sat, 100.0, delta=1.0)
        self.assertAlmostEqual(bri, 25.0, delta=1.0,
                               msg="a colour must not change the level")

    def test_kelvin_alone_zeroes_saturation(self):
        """Otherwise the temperature change would be invisible."""
        self.sink.saturation = p.U16
        LIFX_SERVICE._registry[self.sink.serial]["saturation"] = p.U16

        LifxEvent(target="Sink", kelvin=2700).execute()
        self._settle()
        self.assertEqual(self.sink.saturation, 0)
        self.assertEqual(self.sink.kelvin, 2700)

    def test_kelvin_is_clamped_to_the_bulb_range(self):
        LIFX_SERVICE._registry[self.sink.serial]["kelvin_range"] = [2700, 6500]
        LifxEvent(target="Sink", kelvin=9000).execute()
        self._settle()
        self.assertEqual(self.sink.kelvin, 6500)

    def test_colour_and_power_together(self):
        self.sink.power = False
        LIFX_SERVICE._registry[self.sink.serial]["power"] = False
        LifxEvent(target="Sink", power="on", hue=240, saturation=100,
                  brightness=80).execute()
        self._settle()
        self.assertTrue(self.sink.power)
        hue, sat, bri, _k = p.hsbk_to_pct(self.sink.hue, self.sink.saturation,
                                          self.sink.brightness, self.sink.kelvin)
        self.assertAlmostEqual(hue, 240.0, delta=1.0)
        self.assertAlmostEqual(bri, 80.0, delta=1.0)


class TestFollowUpEvents(LifxStackCase):

    def _settle(self, timeout=6.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not any(t.name == "lifx-event" for t in threading.enumerate()):
                return
            time.sleep(0.02)

    def test_on_complete_fires_with_substituted_placeholders(self):
        LifxEvent(target="Kitchen", brightness=60,
                  on_complete={"type": "toast",
                               "message": "$target ($count) at $brightness%",
                               "nested": {"deep": "$target_type"}}).execute()
        fired = self.recorder.wait_for(1)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["message"], "Kitchen (2) at 60%")
        self.assertEqual(fired[0]["nested"]["deep"], "group",
                         "substitution must recurse into nested dicts")

    def test_on_complete_does_not_mutate_the_stored_event_dict(self):
        """substitute() deep-copies, so the same event can fire repeatedly."""
        template = {"type": "toast", "message": "$target"}
        event = LifxEvent(target="Sink", brightness=40, on_complete=template)
        event.execute()
        self.recorder.wait_for(1)
        self.assertEqual(template["message"], "$target")

    def test_on_error_fires_when_a_bulb_never_answers(self):
        self.island.drop_first = 999          # silent bulb
        LifxEvent(target="Kitchen", brightness=60,
                  on_error={"type": "toast", "message": "$error_code|$failed"},
                  on_complete={"type": "toast", "message": "nope"}).execute()

        fired = self.recorder.wait_for(1, timeout=12)
        self.assertEqual(len(fired), 1)
        code, failed = fired[0]["message"].split("|")
        self.assertEqual(code, "timeout")
        self.assertIn("d073d5000002", failed)

    def test_partial_success_is_reported_as_an_error(self):
        """One bulb of two responding is a failure, not a success."""
        self.island.drop_first = 999
        LifxEvent(target="Kitchen", power="off",
                  on_error={"type": "toast", "message": "$count succeeded"}).execute()
        fired = self.recorder.wait_for(1, timeout=12)
        self.assertEqual(fired[0]["message"], "1 succeeded")
        self.assertFalse(self.sink.power, "the reachable bulb still applied")

    def test_no_follow_up_events_is_fine(self):
        response = LifxEvent(target="Sink", power="off").execute()
        self.assertEqual(response["code"], 200)
        self._settle()
        self.assertEqual(self.recorder.fired, [])


class TestValidation(LifxStackCase):

    def test_out_of_range_values(self):
        for kwargs in ({"brightness": 150}, {"hue": -5}, {"saturation": 900},
                       {"kelvin": 100}, {"duration": -1}):
            response = LifxEvent(target="Sink", **kwargs).execute()
            self.assertEqual(response["code"], 400, kwargs)
            self.assertEqual(response["body"]["error_code"], "bad_request")

    def test_bad_power_word(self):
        response = LifxEvent(target="Sink", power="blinken").execute()
        self.assertEqual(response["code"], 400)

    def test_unparseable_colour(self):
        response = LifxEvent(target="Sink", color="chartreusey").execute()
        self.assertEqual(response["code"], 400)
        self.assertIn("chartreusey", response["body"]["message"])

    def test_nothing_actionable(self):
        response = LifxEvent(target="Sink").execute()
        self.assertEqual(response["code"], 400)

    def test_validation_runs_before_target_resolution(self):
        """A bad value is a 400 even when the target is also wrong."""
        response = LifxEvent(target="Garage", brightness=999).execute()
        self.assertEqual(response["code"], 400)


class TestCompanionEvents(LifxStackCase):

    def test_lifx_list_reports_rooms_and_bulbs(self):
        body = LifxListEvent().execute()["body"]
        self.assertEqual(body["count"], 3)
        self.assertEqual(sorted(r["name"] for r in body["rooms"]),
                         ["Bedroom", "Kitchen"])
        labels = sorted(b["label"] for b in body["bulbs"])
        self.assertEqual(labels, ["Bed", "Island", "Sink"])
        self.assertEqual(body["bulbs"][0]["power"], "on")

    def test_lifx_list_filtered_by_room(self):
        body = LifxListEvent(room="Bedroom").execute()["body"]
        self.assertEqual([b["label"] for b in body["bulbs"]], ["Bed"])

    def test_scene_save_list_apply_remove_round_trip(self):
        import tempfile
        from screens.LIFX.scenes import SceneStore
        tmp = tempfile.mkdtemp(prefix="lifx-int-")
        LIFX_SERVICE._scenes = SceneStore(os.path.join(tmp, "scenes.json"))

        saved = LifxSceneSaveEvent(name="Movie", target="Kitchen").execute()
        self.assertEqual(saved["code"], 200)
        self.assertEqual(saved["body"]["scene"]["bulbs"], 2)

        listed = LifxScenesEvent().execute()["body"]
        self.assertEqual([s["name"] for s in listed["scenes"]], ["Movie"])

        duplicate = LifxSceneSaveEvent(name="Movie").execute()
        self.assertEqual(duplicate["code"], 409)
        self.assertEqual(LifxSceneSaveEvent(name="Movie",
                                            overwrite="1").execute()["code"], 200)

        self.sink.power = False
        LIFX_SERVICE._registry[self.sink.serial]["power"] = False
        applied = LifxEvent(scene="Movie").execute()
        self.assertEqual(applied["code"], 200)
        self.recorder.wait_for(0, timeout=0)
        deadline = time.monotonic() + 6
        while self.sink.power is False and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(self.sink.power, "the scene should have switched it back on")

        removed = LifxSceneRemoveEvent(id=saved["body"]["id"]).execute()
        self.assertEqual(removed["code"], 200)
        self.assertEqual(LifxScenesEvent().execute()["body"]["scenes"], [])

    def test_applying_an_unknown_scene_is_404(self):
        response = LifxEvent(scene="Nonexistent").execute()
        self.assertEqual(response["code"], 404)
        self.assertEqual(response["body"]["error_code"], "scene_not_found")

    def test_scene_remove_unknown_is_404(self):
        self.assertEqual(LifxSceneRemoveEvent(id="nope").execute()["code"], 404)


class TestCoalescing(unittest.TestCase):
    """The queue must collapse a drag but never drop an unrelated command."""

    def setUp(self):
        LIFX_SERVICE._pending.clear()

    def tearDown(self):
        LIFX_SERVICE._pending.clear()

    def test_same_key_replaces_and_keeps_the_newest_value(self):
        for level in range(10):
            LIFX_SERVICE._enqueue("color:a", {"type": "color", "level": level})
        self.assertEqual(len(LIFX_SERVICE._pending), 1)
        self.assertEqual(list(LIFX_SERVICE._pending.values())[0]["level"], 9)

    def test_different_keys_coexist(self):
        LIFX_SERVICE._enqueue("color:a", {"type": "color"})
        LIFX_SERVICE._enqueue("power:a", {"type": "power"})
        self.assertEqual(len(LIFX_SERVICE._pending), 2)

    def test_a_colour_drag_never_drops_a_power_command(self):
        LIFX_SERVICE._enqueue("power:a", {"type": "power", "on": False})
        for _ in range(50):
            LIFX_SERVICE._enqueue("color:a", {"type": "color"})
        keys = list(LIFX_SERVICE._pending)
        self.assertIn("power:a", keys)
        self.assertEqual(len(keys), 2)

    def test_queue_is_fifo(self):
        LIFX_SERVICE._enqueue("first", {"n": 1})
        LIFX_SERVICE._enqueue("second", {"n": 2})
        self.assertEqual(LIFX_SERVICE._pending.popitem(last=False)[1]["n"], 1)

    def test_key_is_order_independent(self):
        a = LIFX_SERVICE._key("color", ["b", "a"])
        b = LIFX_SERVICE._key("color", ["a", "b"])
        self.assertEqual(a, b)


class TestOptimisticMerge(unittest.TestCase):
    """A poll must not snap a value back while the user is still adjusting it."""

    def setUp(self):
        LIFX_SERVICE._registry = {"s1": {"serial": "s1", "brightness": 100,
                                         "power": True, "hue": 0}}
        LIFX_SERVICE._optimistic = {}

    def test_unexpired_optimistic_value_beats_the_poll(self):
        LIFX_SERVICE._mark_optimistic(["s1"], {"brightness": 60000}, seconds=5)
        LIFX_SERVICE._merge_poll("s1", {"brightness": 100, "power": True})
        self.assertEqual(LIFX_SERVICE._registry["s1"]["brightness"], 60000)

    def test_unrelated_fields_still_merge(self):
        LIFX_SERVICE._mark_optimistic(["s1"], {"brightness": 60000}, seconds=5)
        LIFX_SERVICE._merge_poll("s1", {"brightness": 100, "hue": 12345})
        self.assertEqual(LIFX_SERVICE._registry["s1"]["hue"], 12345)

    def test_expired_optimistic_value_yields_to_the_poll(self):
        LIFX_SERVICE._mark_optimistic(["s1"], {"brightness": 60000}, seconds=-1)
        LIFX_SERVICE._merge_poll("s1", {"brightness": 100})
        self.assertEqual(LIFX_SERVICE._registry["s1"]["brightness"], 100)
        self.assertNotIn("s1", LIFX_SERVICE._optimistic)

    def test_marking_is_additive(self):
        LIFX_SERVICE._mark_optimistic(["s1"], {"brightness": 500}, seconds=5)
        LIFX_SERVICE._mark_optimistic(["s1"], {"power": False}, seconds=5)
        LIFX_SERVICE._merge_poll("s1", {"brightness": 100, "power": True})
        self.assertEqual(LIFX_SERVICE._registry["s1"]["brightness"], 500)
        self.assertFalse(LIFX_SERVICE._registry["s1"]["power"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
