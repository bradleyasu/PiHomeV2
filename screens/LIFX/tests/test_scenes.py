"""Headless tests for the LIFX scene store and cloud normalisation.

    python3 screens/LIFX/tests/test_scenes.py
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from screens.LIFX import scenes as s  # noqa: E402
from screens.LIFX.protocol import U16, hsbk_to_pct  # noqa: E402


def bulb(serial, label, group="Kitchen", hue=0, saturation=0, brightness=100,
         kelvin=3500, power=True):
    return {
        "serial": serial, "ip": "192.168.1.9", "port": 56700,
        "label": label, "group": group, "group_id": "gid-" + group.lower(),
        "location": "Home", "location_id": "loc-home",
        "hue": int(hue / 360.0 * U16),
        "saturation": int(saturation / 100.0 * U16),
        "brightness": int(brightness / 100.0 * U16),
        "kelvin": kelvin, "power": power, "online": True,
    }


def registry():
    return {
        "d073d5000001": bulb("d073d5000001", "Sink", hue=120, saturation=100,
                             brightness=80),
        "d073d5000002": bulb("d073d5000002", "Island", brightness=40),
        "d073d5000003": bulb("d073d5000003", "Bed", group="Bedroom", power=False),
    }


class StoreCase(unittest.TestCase):
    """Points SCENES_FILE at a temp dir so nothing touches the real cache."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lifx-scenes-")
        self.path = os.path.join(self.tmp, "nested", "lifx_scenes.json")
        self._original = s.SCENES_FILE
        s.SCENES_FILE = self.path
        self.store = s.SceneStore()

    def tearDown(self):
        s.SCENES_FILE = self._original
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestSnapshots(StoreCase):

    def test_save_creates_the_cache_directory(self):
        """A fresh checkout has no cache/ - the store must create it."""
        self.assertFalse(os.path.exists(self.path))
        self.store.save_snapshot("Movie Night", registry())
        self.assertTrue(os.path.exists(self.path))

    def test_snapshot_captures_current_state(self):
        scene = self.store.save_snapshot("Movie Night", registry())
        self.assertEqual(scene["name"], "Movie Night")
        self.assertEqual(scene["source"], s.SOURCE_LOCAL)
        self.assertEqual(len(scene["states"]), 3)

        by_selector = {st["selector"]: st for st in scene["states"]}
        sink = by_selector["id:d073d5000001"]
        self.assertAlmostEqual(sink["hue"], 120.0, delta=0.5)
        self.assertAlmostEqual(sink["saturation"], 100.0, delta=0.5)
        self.assertAlmostEqual(sink["brightness"], 80.0, delta=0.5)
        self.assertTrue(sink["power"])
        self.assertFalse(by_selector["id:d073d5000003"]["power"])

    def test_snapshot_of_a_subset(self):
        scene = self.store.save_snapshot("Kitchen Only", registry(),
                                         serials=["d073d5000001"])
        self.assertEqual([st["selector"] for st in scene["states"]],
                         ["id:d073d5000001"])

    def test_resaving_the_same_name_replaces_rather_than_duplicates(self):
        first = self.store.save_snapshot("Evening", registry())
        reg = registry()
        reg["d073d5000001"]["brightness"] = int(0.10 * U16)
        second = self.store.save_snapshot("Evening", reg)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.list()), 1)
        updated = {st["selector"]: st for st in second["states"]}
        self.assertAlmostEqual(updated["id:d073d5000001"]["brightness"], 10.0,
                               delta=0.5)

    def test_blank_name_rejected(self):
        for name in ("", "   ", None):
            with self.assertRaises(ValueError):
                self.store.save_snapshot(name, registry())

    def test_empty_registry_rejected(self):
        with self.assertRaises(ValueError):
            self.store.save_snapshot("Nothing", {})

    def test_unknown_serials_are_skipped(self):
        with self.assertRaises(ValueError):
            self.store.save_snapshot("Ghost", registry(), serials=["deadbeef0000"])


class TestStoreCrud(StoreCase):

    def test_round_trip_through_disk(self):
        self.store.save_snapshot("Evening", registry())
        reopened = s.SceneStore(self.path)
        self.assertEqual([sc["name"] for sc in reopened.list()], ["Evening"])

    def test_get_by_name_is_case_insensitive(self):
        self.store.save_snapshot("Movie Night", registry())
        for key in ("Movie Night", "movie night", "  MOVIE NIGHT  "):
            self.assertIsNotNone(self.store.get(key), key)

    def test_get_by_id(self):
        scene = self.store.save_snapshot("Evening", registry())
        self.assertEqual(self.store.get(scene["id"])["name"], "Evening")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("nope"))
        self.assertIsNone(self.store.get(""))
        self.assertIsNone(self.store.get(None))

    def test_remove_by_id_and_by_name(self):
        scene = self.store.save_snapshot("Evening", registry())
        self.assertTrue(self.store.remove(scene["id"]))
        self.assertEqual(self.store.list(), [])

        self.store.save_snapshot("Morning", registry())
        self.assertTrue(self.store.remove("morning"))
        self.assertEqual(self.store.list(), [])

    def test_remove_missing_returns_false(self):
        self.assertFalse(self.store.remove("nope"))

    def test_local_scenes_sort_before_cloud(self):
        self.store.save_snapshot("Zebra", registry())
        self.store.merge_cloud([cloud_scene("aaa-1", "Apple")])
        self.assertEqual([sc["name"] for sc in self.store.list()],
                         ["Zebra", "Apple"])

    def test_corrupt_file_is_ignored_not_fatal(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as handle:
            handle.write("{not json")
        self.assertEqual(s.SceneStore(self.path).list(), [])


def cloud_scene(uuid_, name, selector="id:d073d5000001", hue=250.0,
                saturation=0.5, brightness=0.5, kelvin=3500, power="on"):
    return {
        "uuid": uuid_,
        "name": name,
        "updated_at": 1700000000,
        "states": [{
            "selector": selector,
            "power": power,
            "brightness": brightness,
            "color": {"hue": hue, "saturation": saturation, "kelvin": kelvin},
        }],
    }


class TestCloudNormalisation(unittest.TestCase):

    def test_fractions_become_percentages(self):
        """The cloud reports saturation/brightness as 0-1, we store 0-100."""
        scene = s.normalize_cloud_scene(cloud_scene("u1", "Movie"))
        state = scene["states"][0]
        self.assertEqual(scene["source"], s.SOURCE_CLOUD)
        self.assertEqual(scene["id"], "u1")
        self.assertAlmostEqual(state["hue"], 250.0)
        self.assertAlmostEqual(state["saturation"], 50.0)
        self.assertAlmostEqual(state["brightness"], 50.0)
        self.assertEqual(state["kelvin"], 3500)
        self.assertTrue(state["power"])

    def test_power_off_state(self):
        scene = s.normalize_cloud_scene(cloud_scene("u1", "Movie", power="off"))
        self.assertFalse(scene["states"][0]["power"])

    def test_missing_brightness_defaults_to_full(self):
        raw = cloud_scene("u1", "Movie")
        del raw["states"][0]["brightness"]
        del raw["states"][0]["color"]["saturation"]
        state = s.normalize_cloud_scene(raw)["states"][0]
        self.assertEqual(state["brightness"], 100.0)

    def test_unusable_payloads_return_none(self):
        self.assertIsNone(s.normalize_cloud_scene(None))
        self.assertIsNone(s.normalize_cloud_scene({}))
        self.assertIsNone(s.normalize_cloud_scene({"uuid": "u1", "name": "x"}))
        self.assertIsNone(s.normalize_cloud_scene({"uuid": "u1", "states": []}))

    def test_hue_is_wrapped(self):
        scene = s.normalize_cloud_scene(cloud_scene("u1", "Movie", hue=400.0))
        self.assertAlmostEqual(scene["states"][0]["hue"], 40.0)


class TestMergeCloud(StoreCase):

    def test_merge_adds_cloud_scenes(self):
        count = self.store.merge_cloud([cloud_scene("u1", "Movie"),
                                        cloud_scene("u2", "Dinner")])
        self.assertEqual(count, 2)
        self.assertEqual(sorted(sc["name"] for sc in self.store.list()),
                         ["Dinner", "Movie"])

    def test_merge_upserts_by_uuid(self):
        self.store.merge_cloud([cloud_scene("u1", "Movie")])
        self.store.merge_cloud([cloud_scene("u1", "Movie Night")])
        self.assertEqual([sc["name"] for sc in self.store.list()], ["Movie Night"])

    def test_merge_never_touches_local_scenes(self):
        local = self.store.save_snapshot("Evening", registry())
        self.store.merge_cloud([cloud_scene("u1", "Movie")])
        self.assertIsNotNone(self.store.get(local["id"]))
        self.store.merge_cloud([])
        self.assertIsNotNone(self.store.get(local["id"]),
                             "an empty cloud sync must not delete local scenes")

    def test_scene_deleted_upstream_is_dropped(self):
        self.store.merge_cloud([cloud_scene("u1", "Movie"),
                                cloud_scene("u2", "Dinner")])
        self.store.merge_cloud([cloud_scene("u1", "Movie")])
        self.assertEqual([sc["name"] for sc in self.store.list()], ["Movie"])

    def test_unusable_cloud_entries_are_skipped(self):
        count = self.store.merge_cloud([cloud_scene("u1", "Movie"), {}, None])
        self.assertEqual(count, 1)


class TestResolveSceneStates(unittest.TestCase):

    def scene(self, *states):
        return {"id": "x", "name": "Test", "source": "cloud", "states": list(states)}

    def state(self, selector, hue=0.0, saturation=0.0, brightness=100.0,
              kelvin=3500, power=True):
        return {"selector": selector, "hue": hue, "saturation": saturation,
                "brightness": brightness, "kelvin": kelvin, "power": power}

    def test_id_selector(self):
        applies, unresolved = s.resolve_scene_states(
            self.scene(self.state("id:d073d5000001", hue=120, saturation=100)),
            registry())
        self.assertEqual(unresolved, [])
        self.assertEqual(len(applies), 1)
        serial, hsbk, power = applies[0]
        self.assertEqual(serial, "d073d5000001")
        self.assertTrue(power)
        hue, sat, _bri, _k = hsbk_to_pct(*hsbk)
        self.assertAlmostEqual(hue, 120.0, delta=0.5)
        self.assertAlmostEqual(sat, 100.0, delta=0.5)

    def test_group_id_selector(self):
        applies, unresolved = s.resolve_scene_states(
            self.scene(self.state("group_id:gid-kitchen")), registry())
        self.assertEqual(unresolved, [])
        self.assertEqual([a[0] for a in applies],
                         ["d073d5000001", "d073d5000002"])

    def test_group_name_and_label_selectors(self):
        for selector, expected in [("group:Bedroom", ["d073d5000003"]),
                                   ("label:Island", ["d073d5000002"]),
                                   ("location:Home", ["d073d5000001",
                                                      "d073d5000002",
                                                      "d073d5000003"])]:
            applies, _ = s.resolve_scene_states(
                self.scene(self.state(selector)), registry())
            self.assertEqual([a[0] for a in applies], expected, selector)

    def test_all_selector(self):
        applies, _ = s.resolve_scene_states(
            self.scene(self.state("all")), registry())
        self.assertEqual(len(applies), 3)

    def test_bare_selector_is_treated_as_a_label(self):
        applies, _ = s.resolve_scene_states(
            self.scene(self.state("Island")), registry())
        self.assertEqual([a[0] for a in applies], ["d073d5000002"])

    def test_unresolvable_selector_is_reported_not_dropped_silently(self):
        applies, unresolved = s.resolve_scene_states(
            self.scene(self.state("id:aabbccddeeff"),
                       self.state("id:d073d5000001")), registry())
        self.assertEqual(unresolved, ["id:aabbccddeeff"])
        self.assertEqual(len(applies), 1)

    def test_a_specific_state_overrides_a_broad_one(self):
        """The app layers a narrow selector over 'all'; later states win."""
        applies, _ = s.resolve_scene_states(
            self.scene(self.state("all", brightness=10.0),
                       self.state("id:d073d5000001", brightness=90.0)),
            registry())
        levels = {serial: hsbk_to_pct(*hsbk)[2] for serial, hsbk, _p in applies}
        self.assertAlmostEqual(levels["d073d5000001"], 90.0, delta=0.5)
        self.assertAlmostEqual(levels["d073d5000002"], 10.0, delta=0.5)

    def test_power_off_states_are_preserved(self):
        applies, _ = s.resolve_scene_states(
            self.scene(self.state("id:d073d5000001", power=False)), registry())
        self.assertFalse(applies[0][2])

    def test_empty_scene(self):
        self.assertEqual(s.resolve_scene_states({}, registry()), ([], []))
        self.assertEqual(s.resolve_scene_states(None, registry()), ([], []))


class TestSwatches(unittest.TestCase):

    def test_swatches_skip_bulbs_that_are_off(self):
        scene = {"states": [
            {"selector": "a", "hue": 0, "saturation": 100, "brightness": 100,
             "kelvin": 3500, "power": False},
            {"selector": "b", "hue": 0, "saturation": 100, "brightness": 100,
             "kelvin": 3500, "power": True},
        ]}
        self.assertEqual(s.scene_swatches(scene), [(255, 0, 0)])

    def test_swatches_are_capped(self):
        scene = {"states": [
            {"selector": str(i), "hue": i * 30, "saturation": 100,
             "brightness": 100, "kelvin": 3500, "power": True}
            for i in range(10)
        ]}
        self.assertEqual(len(s.scene_swatches(scene, limit=4)), 4)


class TestLifxCloud(unittest.TestCase):

    def test_unavailable_without_a_token(self):
        self.assertFalse(s.LifxCloud("").available)
        self.assertFalse(s.LifxCloud(None).available)
        self.assertFalse(s.LifxCloud("   ").available)

    def test_availability_tracks_the_requests_import(self):
        """Cloud sync needs both a token and requests - the app venv has both."""
        try:
            import requests  # noqa: F401
            has_requests = True
        except ImportError:
            has_requests = False
        self.assertEqual(s.LifxCloud("tok").available, has_requests)

    def test_calls_without_a_token_raise(self):
        cloud = s.LifxCloud("")
        with self.assertRaises(RuntimeError):
            cloud.list_scenes()
        with self.assertRaises(RuntimeError):
            cloud.activate("uuid")


if __name__ == "__main__":
    unittest.main(verbosity=2)
