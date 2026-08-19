"""Headless tests for LIFX target resolution.

    python3 screens/LIFX/tests/test_targeting.py
"""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from screens.LIFX.protocol import U16  # noqa: E402
from screens.LIFX.targeting import (  # noqa: E402
    KIND_ALL,
    KIND_BULB,
    KIND_GROUP,
    TargetError,
    group_index,
    merge_kelvin_ranges,
    resolve_target,
    summarize,
)


def bulb(serial, label, group="Kitchen", power=True, brightness=100,
         color=True, kelvin=3500, kelvin_range=(1500, 9000), online=True,
         location="Home", hue=0, saturation=0):
    return {
        "serial": serial, "ip": "192.168.1.9", "port": 56700,
        "label": label, "group": group, "group_id": group.lower(),
        "location": location, "location_id": "home",
        "product": 27, "color": color, "kelvin_range": list(kelvin_range),
        "hue": hue, "saturation": saturation,
        "brightness": int(brightness / 100.0 * U16), "kelvin": kelvin,
        "power": power, "seen_at": 0.0, "online": online,
    }


def registry():
    """A deliberately nasty fixture: a bulb named "Kitchen" inside group "Kitchen"."""
    return {
        "d073d5000001": bulb("d073d5000001", "Kitchen", group="Kitchen"),
        "d073d5000002": bulb("d073d5000002", "Island", group="Kitchen"),
        "d073d5000003": bulb("d073d5000003", "Bed", group="Bedroom", power=False),
        "d073d5000004": bulb("d073d5000004", "Bedside", group="Bedroom"),
        "d073d5000005": bulb("d073d5000005", "Lamp", group=""),
    }


class TestResolveAll(unittest.TestCase):

    def test_empty_registry_is_503(self):
        with self.assertRaises(TargetError) as ctx:
            resolve_target({}, "anything")
        self.assertEqual(ctx.exception.code, 503)
        self.assertEqual(ctx.exception.error_code, "no_devices")

    def test_all_synonyms(self):
        reg = registry()
        for target in (None, "", "all", "ALL", "*", "  all  "):
            serials, kind, name = resolve_target(reg, target)
            self.assertEqual(kind, KIND_ALL, repr(target))
            self.assertEqual(len(serials), 5)
            self.assertEqual(name, "All Lights")

    def test_all_skips_offline_bulbs(self):
        reg = registry()
        reg["d073d5000005"]["online"] = False
        serials, _kind, _name = resolve_target(reg, "all")
        self.assertEqual(len(serials), 4)
        self.assertNotIn("d073d5000005", serials)

    def test_all_offline_is_503(self):
        reg = registry()
        for entry in reg.values():
            entry["online"] = False
        with self.assertRaises(TargetError) as ctx:
            resolve_target(reg, "all")
        self.assertEqual(ctx.exception.code, 503)


class TestResolveNames(unittest.TestCase):

    def test_group_beats_bulb_on_an_exact_tie(self):
        """"Kitchen" is both a room and a bulb - the room wins."""
        serials, kind, name = resolve_target(registry(), "Kitchen")
        self.assertEqual(kind, KIND_GROUP)
        self.assertEqual(name, "Kitchen")
        self.assertEqual(len(serials), 2)

    def test_target_type_bulb_forces_the_other_reading(self):
        serials, kind, name = resolve_target(registry(), "Kitchen",
                                             target_type="bulb")
        self.assertEqual(kind, KIND_BULB)
        self.assertEqual(serials, ["d073d5000001"])
        self.assertEqual(name, "Kitchen")

    def test_target_type_group_will_not_match_a_bulb(self):
        with self.assertRaises(TargetError) as ctx:
            resolve_target(registry(), "Island", target_type="group")
        self.assertEqual(ctx.exception.code, 404)
        self.assertEqual(ctx.exception.error_code, "group_not_found")

    def test_case_insensitive(self):
        for target in ("island", "ISLAND", "IsLaNd"):
            serials, kind, _ = resolve_target(registry(), target)
            self.assertEqual(kind, KIND_BULB)
            self.assertEqual(serials, ["d073d5000002"])

    def test_bulb_name_unique_to_one_bulb(self):
        serials, kind, name = resolve_target(registry(), "Lamp")
        self.assertEqual((serials, kind, name), (["d073d5000005"], KIND_BULB, "Lamp"))

    def test_location_resolves_as_a_group(self):
        serials, kind, name = resolve_target(registry(), "Home")
        self.assertEqual(kind, KIND_GROUP)
        self.assertEqual(name, "Home")
        self.assertEqual(len(serials), 5)

    def test_unknown_name_is_404(self):
        with self.assertRaises(TargetError) as ctx:
            resolve_target(registry(), "Garage")
        self.assertEqual(ctx.exception.code, 404)
        self.assertEqual(ctx.exception.error_code, "bulb_not_found")
        self.assertIn("Garage", ctx.exception.message)

    def test_bad_target_type_is_400(self):
        with self.assertRaises(TargetError) as ctx:
            resolve_target(registry(), "Kitchen", target_type="nonsense")
        self.assertEqual(ctx.exception.code, 400)

    def test_empty_target_with_explicit_type_is_400(self):
        with self.assertRaises(TargetError) as ctx:
            resolve_target(registry(), "", target_type="bulb")
        self.assertEqual(ctx.exception.code, 400)

    def test_duplicate_bulb_labels_resolve_to_the_set(self):
        reg = registry()
        reg["d073d5000009"] = bulb("d073d5000009", "Island", group="Bar")
        serials, kind, _name = resolve_target(reg, "Island")
        self.assertEqual(kind, KIND_GROUP)
        self.assertEqual(len(serials), 2)


class TestResolveSerials(unittest.TestCase):

    def test_bare_serial(self):
        serials, kind, name = resolve_target(registry(), "d073d5000002")
        self.assertEqual((serials, kind, name), (["d073d5000002"], KIND_BULB, "Island"))

    def test_serial_with_separators_and_case(self):
        serials, _kind, _name = resolve_target(registry(), "D0:73:D5:00:00:02")
        self.assertEqual(serials, ["d073d5000002"])

    def test_unknown_serial_is_404(self):
        with self.assertRaises(TargetError) as ctx:
            resolve_target(registry(), "aabbccddeeff")
        self.assertEqual(ctx.exception.code, 404)


class TestPrefixMatching(unittest.TestCase):

    def test_unique_prefix_matches(self):
        serials, kind, name = resolve_target(registry(), "Bedr")
        self.assertEqual(kind, KIND_GROUP)
        self.assertEqual(name, "Bedroom")
        self.assertEqual(len(serials), 2)

    def test_unique_bulb_prefix(self):
        serials, kind, _name = resolve_target(registry(), "Lam")
        self.assertEqual((serials, kind), (["d073d5000005"], KIND_BULB))

    def test_exact_match_beats_a_fuzzy_prefix(self):
        """"Bed" also prefixes Bedroom and Bedside, but it names a bulb exactly."""
        serials, kind, name = resolve_target(registry(), "Bed")
        self.assertEqual((serials, kind, name), (["d073d5000003"], KIND_BULB, "Bed"))

    def test_ambiguous_prefix_is_409_with_candidates(self):
        """"Be" prefixes the room Bedroom and the bulbs Bed and Bedside."""
        with self.assertRaises(TargetError) as ctx:
            resolve_target(registry(), "Be")
        self.assertEqual(ctx.exception.code, 409)
        self.assertEqual(ctx.exception.error_code, "ambiguous_target")
        self.assertEqual(sorted(ctx.exception.candidates),
                         ["Bed", "Bedroom", "Bedside"])

    def test_target_type_disambiguates_a_409(self):
        serials, kind, name = resolve_target(registry(), "Be",
                                             target_type="group")
        self.assertEqual((kind, name), (KIND_GROUP, "Bedroom"))
        self.assertEqual(len(serials), 2)


class TestGroupIndex(unittest.TestCase):

    def test_rooms_sorted_with_ungrouped_last(self):
        rooms = group_index(registry())
        self.assertEqual([r["name"] for r in rooms],
                         ["Bedroom", "Kitchen", "Ungrouped"])

    def test_room_stats(self):
        rooms = {r["name"]: r for r in group_index(registry())}
        self.assertEqual(rooms["Kitchen"]["count"], 2)
        self.assertEqual(rooms["Kitchen"]["on_count"], 2)
        self.assertTrue(rooms["Kitchen"]["any_on"])
        self.assertEqual(rooms["Bedroom"]["on_count"], 1)

    def test_bulbs_within_a_room_sort_by_label(self):
        rooms = {r["name"]: r for r in group_index(registry())}
        labels = [registry()[s]["label"] for s in rooms["Bedroom"]["serials"]]
        self.assertEqual(labels, ["Bed", "Bedside"])

    def test_empty_registry_yields_no_rooms(self):
        self.assertEqual(group_index({}), [])


class TestSummarize(unittest.TestCase):

    def test_empty_selection(self):
        stats = summarize(registry(), [])
        self.assertEqual(stats["count"], 0)
        self.assertFalse(stats["any_on"])

    def test_counts_and_flags(self):
        reg = registry()
        stats = summarize(reg, ["d073d5000003", "d073d5000004"])
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["on_count"], 1)
        self.assertTrue(stats["any_on"])
        self.assertFalse(stats["all_on"])

    def test_brightness_averages_only_lit_bulbs(self):
        """An off bulb reporting its last level must not drag the slider down."""
        reg = registry()
        reg["d073d5000003"]["brightness"] = 0
        reg["d073d5000004"]["brightness"] = int(0.80 * U16)
        stats = summarize(reg, ["d073d5000003", "d073d5000004"])
        self.assertAlmostEqual(stats["brightness"], 80.0, delta=0.1)

    def test_brightness_falls_back_to_all_when_nothing_is_lit(self):
        reg = registry()
        for serial in ("d073d5000003", "d073d5000004"):
            reg[serial]["power"] = False
            reg[serial]["brightness"] = int(0.50 * U16)
        stats = summarize(reg, ["d073d5000003", "d073d5000004"])
        self.assertAlmostEqual(stats["brightness"], 50.0, delta=0.1)

    def test_supports_color_is_true_if_any_bulb_does(self):
        reg = registry()
        reg["d073d5000001"]["color"] = False
        self.assertTrue(summarize(reg, ["d073d5000001", "d073d5000002"])["supports_color"])
        reg["d073d5000002"]["color"] = False
        self.assertFalse(summarize(reg, ["d073d5000001", "d073d5000002"])["supports_color"])

    def test_colour_comes_from_a_lit_colour_capable_bulb(self):
        reg = registry()
        reg["d073d5000001"]["color"] = False
        reg["d073d5000002"]["hue"] = U16 // 2      # 180 degrees
        reg["d073d5000002"]["saturation"] = U16
        stats = summarize(reg, ["d073d5000001", "d073d5000002"])
        self.assertAlmostEqual(stats["hue"], 180.0, delta=0.5)
        self.assertAlmostEqual(stats["saturation"], 100.0, delta=0.5)


class TestKelvinRanges(unittest.TestCase):

    def test_intersection_of_overlapping_ranges(self):
        entries = [{"kelvin_range": (1500, 9000)}, {"kelvin_range": (2700, 6500)}]
        self.assertEqual(merge_kelvin_ranges(entries), (2700, 6500))

    def test_non_overlapping_ranges_widen_instead_of_collapsing(self):
        """A slider with no travel is worse than one the bulb will clamp itself."""
        entries = [{"kelvin_range": (2700, 2700)}, {"kelvin_range": (1500, 4000)}]
        self.assertEqual(merge_kelvin_ranges(entries), (1500, 4000))

    def test_missing_or_garbage_range_falls_back(self):
        self.assertEqual(merge_kelvin_ranges([{}]), (1500, 9000))
        self.assertEqual(merge_kelvin_ranges([{"kelvin_range": "nope"}]), (1500, 9000))

    def test_inverted_range_is_normalised(self):
        self.assertEqual(merge_kelvin_ranges([{"kelvin_range": (6500, 2700)}]),
                         (2700, 6500))


if __name__ == "__main__":
    unittest.main(verbosity=2)
