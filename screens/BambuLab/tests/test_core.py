"""Headless tests for the BambuLab state logic.

No Kivy, no paho-mqtt, no printer, no GL context:

    venv/bin/python screens/BambuLab/tests/test_core.py
"""

import datetime
import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from screens.BambuLab.bambustate import (  # noqa: E402
    format_alerts,
    format_eta,
    format_finish,
    format_temp,
    hex_to_rgba,
    new_snapshot,
    normalize_trigger,
    parse_print,
    placeholder_values,
    resolve_filament,
    state_label,
    substitute,
    triggers_fired,
)


def seeded(**overrides):
    """A snapshot that has already taken one report — the baseline for a transition."""
    snap = new_snapshot()
    snap["seeded"] = True
    snap["connected"] = True
    snap.update(overrides)
    return snap


class TestNormalizeTrigger(unittest.TestCase):

    def test_canonical_tokens_pass_through(self):
        for token in ("IDLE", "RUNNING", "PAUSE", "FINISH", "FAILED", "ERROR",
                      "ONLINE", "OFFLINE", "PREPARE", "SLICING"):
            self.assertEqual(normalize_trigger(token), token)

    def test_case_and_whitespace_insensitive(self):
        self.assertEqual(normalize_trigger("  running "), "RUNNING")

    def test_human_aliases(self):
        self.assertEqual(normalize_trigger("printing"), "RUNNING")
        self.assertEqual(normalize_trigger("complete"), "FINISH")
        self.assertEqual(normalize_trigger("done"), "FINISH")
        self.assertEqual(normalize_trigger("paused"), "PAUSE")
        self.assertEqual(normalize_trigger("disconnected"), "OFFLINE")

    def test_unknown_and_empty_are_rejected(self):
        self.assertIsNone(normalize_trigger("bogus"))
        self.assertIsNone(normalize_trigger(""))
        self.assertIsNone(normalize_trigger(None))


class TestTriggersFired(unittest.TestCase):

    def test_gcode_transition_fires_once(self):
        prev = seeded(gcode_state="RUNNING")
        new = seeded(gcode_state="FINISH")
        self.assertEqual(triggers_fired(prev, new), ["FINISH"])
        # Staying in the same state must not re-fire.
        self.assertEqual(triggers_fired(new, seeded(gcode_state="FINISH")), [])

    def test_unseeded_baseline_never_fires(self):
        """The first report after a connect establishes state without firing."""
        prev = new_snapshot()                      # not seeded
        prev["connected"] = True                   # isolate from the ONLINE edge
        new = seeded(gcode_state="FINISH")
        self.assertEqual(triggers_fired(prev, new), [])

    def test_none_prev_never_fires(self):
        self.assertEqual(triggers_fired(None, seeded(gcode_state="FINISH")), [])

    def test_error_fires_on_clear_to_set_edge(self):
        prev = seeded(alert_active=False)
        raised = seeded(alert_active=True)
        self.assertEqual(triggers_fired(prev, raised), ["ERROR"])
        # Still in alert — no repeat.
        self.assertEqual(triggers_fired(raised, seeded(alert_active=True)), [])
        # Clearing is not an ERROR.
        self.assertEqual(triggers_fired(raised, seeded(alert_active=False)), [])

    def test_error_is_independent_of_failed(self):
        """A runout raises ERROR without the job being FAILED, and vice versa."""
        prev = seeded(gcode_state="RUNNING", alert_active=False)
        new = seeded(gcode_state="RUNNING", alert_active=True)
        self.assertEqual(triggers_fired(prev, new), ["ERROR"])

    def test_online_offline_edges(self):
        down = seeded(connected=False)
        up = seeded(connected=True)
        self.assertEqual(triggers_fired(down, up), ["ONLINE"])
        self.assertEqual(triggers_fired(up, down), ["OFFLINE"])
        self.assertEqual(triggers_fired(up, seeded(connected=True)), [])

    def test_connection_edges_fire_before_first_report(self):
        """ONLINE/OFFLINE do not depend on a seeded snapshot."""
        prev = new_snapshot()                       # unseeded, disconnected
        new = new_snapshot()
        new["connected"] = True
        self.assertEqual(triggers_fired(prev, new), ["ONLINE"])

    def test_simultaneous_state_and_error(self):
        prev = seeded(gcode_state="RUNNING", alert_active=False)
        new = seeded(gcode_state="FAILED", alert_active=True)
        self.assertEqual(sorted(triggers_fired(prev, new)), ["ERROR", "FAILED"])

    def test_unmapped_state_does_not_fire(self):
        prev = seeded(gcode_state="RUNNING")
        new = seeded(gcode_state="SOMETHING_NEW")
        self.assertEqual(triggers_fired(prev, new), [])


class TestSubstitute(unittest.TestCase):

    def test_replaces_named_placeholders(self):
        event = {"type": "toast", "message": "$job is $progress% done"}
        out = substitute(event, {"job": "benchy.3mf", "progress": "42"})
        self.assertEqual(out["message"], "benchy.3mf is 42% done")

    def test_longer_keys_win_over_prefixes(self):
        """$layer_total must not be eaten by $layer."""
        out = substitute({"m": "$layer/$layer_total"},
                         {"layer": "10", "layer_total": "250"})
        self.assertEqual(out["m"], "10/250")

    def test_recurses_into_nested_events_and_lists(self):
        event = {"type": "multi", "events": [{"type": "toast", "message": "$state"}]}
        out = substitute(event, {"state": "FINISH"})
        self.assertEqual(out["events"][0]["message"], "FINISH")

    def test_does_not_mutate_the_stored_rule(self):
        event = {"type": "toast", "message": "$state"}
        substitute(event, {"state": "FINISH"})
        self.assertEqual(event["message"], "$state")

    def test_non_strings_are_left_alone(self):
        out = substitute({"timeout": 5, "level": None, "ok": True}, {"state": "X"})
        self.assertEqual(out, {"timeout": 5, "level": None, "ok": True})

    def test_unknown_placeholder_is_left_as_is(self):
        out = substitute({"m": "$nope"}, {"state": "X"})
        self.assertEqual(out["m"], "$nope")


class TestPlaceholderValues(unittest.TestCase):

    def test_values_from_snapshot(self):
        snap = seeded(gcode_state="RUNNING", state_label="PRINTING",
                      job_name="benchy.3mf", progress=42, layer_current=10,
                      layer_total=250, eta_minutes=95, nozzle=219.6, bed=60.2)
        vals = placeholder_values(snap)
        self.assertEqual(vals["state"], "RUNNING")
        self.assertEqual(vals["state_label"], "PRINTING")
        self.assertEqual(vals["job"], "benchy.3mf")
        self.assertEqual(vals["progress"], "42")
        self.assertEqual(vals["layer"], "10")
        self.assertEqual(vals["layer_total"], "250")
        self.assertEqual(vals["eta"], "95")
        self.assertEqual(vals["eta_text"], "ETA  1h 35m")
        self.assertEqual(vals["nozzle"], "220")
        self.assertEqual(vals["bed"], "60")

    def test_blank_snapshot_is_safe(self):
        vals = placeholder_values(new_snapshot())
        self.assertEqual(vals["progress"], "0")
        self.assertEqual(vals["finish"], "")


class TestFormatters(unittest.TestCase):

    def test_eta(self):
        self.assertEqual(format_eta(0), "—")
        self.assertEqual(format_eta(-5), "—")
        self.assertEqual(format_eta(45), "ETA  45 min")
        self.assertEqual(format_eta(120), "ETA  2h")
        self.assertEqual(format_eta(95), "ETA  1h 35m")

    def test_temp(self):
        self.assertEqual(format_temp(219.6, 220), "220° / 220°C")
        self.assertEqual(format_temp(24.35, 0), "24.4°C")

    def test_finish_only_while_running(self):
        now = datetime.datetime(2026, 1, 1, 14, 0)
        self.assertEqual(format_finish(30, "RUNNING", now), "Done 2:30 PM")
        self.assertEqual(format_finish(30, "PAUSE", now), "")
        self.assertEqual(format_finish(0, "RUNNING", now), "")

    def test_state_label_falls_back_to_raw_token(self):
        self.assertEqual(state_label("RUNNING"), "PRINTING")
        self.assertEqual(state_label("PREPARE"), "PREPARING")
        self.assertEqual(state_label("WEIRD"), "WEIRD")


class TestFormatAlerts(unittest.TestCase):

    def test_clear(self):
        out = format_alerts([], 0)
        self.assertFalse(out["active"])
        self.assertEqual(out["text"], "")

    def test_print_error_only(self):
        out = format_alerts(None, 0x0300_4001)
        self.assertTrue(out["active"])
        self.assertEqual(out["text"], "Print Error  0x03004001")
        self.assertTrue(out["severe"])

    def test_hms_code_formatting(self):
        out = format_alerts([{"attr": 0x0C000200, "code": 0x00030001}], 0)
        self.assertEqual(out["text"], "HMS  0C00_0200_0003_0001")
        self.assertFalse(out["severe"])          # severity 3 = common -> amber

    def test_hms_severity_fatal_is_severe(self):
        out = format_alerts([{"attr": 0x0C000200, "code": 0x00010001}], 0)
        self.assertTrue(out["severe"])

    def test_multiple_codes_are_counted(self):
        out = format_alerts([{"attr": 1, "code": 0x00020001},
                             {"attr": 2, "code": 0x00030001}], 0)
        self.assertIn("(+1 more)", out["text"])

    def test_zero_pairs_are_ignored(self):
        self.assertFalse(format_alerts([{"attr": 0, "code": 0}], 0)["active"])


class TestFilament(unittest.TestCase):

    def test_selects_the_active_tray(self):
        ams = {"tray_now": "2", "ams": [{"tray": [
            {"id": "0", "tray_type": "PLA", "tray_color": "FF0000FF"},
            {"id": "2", "tray_type": "PETG", "tray_sub_brands": "PETG HF",
             "tray_color": "00FF00FF"},
        ]}]}
        name, rgba = resolve_filament(ams, None)
        self.assertEqual(name, "PETG HF")
        self.assertEqual(rgba, [0.0, 1.0, 0.0, 1.0])

    def test_external_spool(self):
        name, rgba = resolve_filament(
            {"tray_now": "254"}, {"tray_type": "ABS", "tray_color": "0000FFFF"})
        self.assertEqual(name, "ABS")
        self.assertEqual(rgba, [0.0, 0.0, 1.0, 1.0])

    def test_falls_back_to_first_loaded_tray(self):
        ams = {"tray_now": "9", "ams": [{"tray": [
            {"id": "0", "tray_type": "PLA", "tray_color": "FFFFFFFF"}]}]}
        name, _ = resolve_filament(ams, None)
        self.assertEqual(name, "PLA")

    def test_nothing_loaded(self):
        self.assertEqual(resolve_filament({"tray_now": "0", "ams": []}, None),
                         (None, None))

    def test_hex_to_rgba_edge_cases(self):
        self.assertIsNone(hex_to_rgba(""))
        self.assertIsNone(hex_to_rgba("FFF"))
        self.assertIsNone(hex_to_rgba("FF000000"))     # fully transparent
        self.assertIsNone(hex_to_rgba("ZZZZZZ"))
        self.assertEqual(hex_to_rgba("FF0000"), [1.0, 0.0, 0.0, 1.0])


class TestParsePrint(unittest.TestCase):

    def test_extracts_fields_and_seeds(self):
        snap = parse_print({
            "gcode_state": "RUNNING", "mc_percent": 42, "layer_num": 10,
            "total_layer_num": 250, "mc_remaining_time": 95,
            "nozzle_temper": 219.6, "nozzle_target_temper": 220,
            "bed_temper": 60.0, "bed_target_temper": 60, "spd_mag": 100,
            "subtask_name": "benchy.3mf",
        }, new_snapshot())
        self.assertTrue(snap["seeded"])
        self.assertEqual(snap["gcode_state"], "RUNNING")
        self.assertEqual(snap["state_label"], "PRINTING")
        self.assertEqual(snap["progress"], 42)
        self.assertEqual(snap["layer_total"], 250)
        self.assertEqual(snap["job_name"], "benchy.3mf")

    def test_deltas_keep_previous_values(self):
        """P1 sends only changed fields — absent keys must not reset state."""
        first = parse_print({"gcode_state": "RUNNING", "mc_percent": 42,
                             "subtask_name": "benchy.3mf"}, new_snapshot())
        second = parse_print({"mc_percent": 43}, first)
        self.assertEqual(second["gcode_state"], "RUNNING")
        self.assertEqual(second["job_name"], "benchy.3mf")
        self.assertEqual(second["progress"], 43)

    def test_does_not_mutate_the_previous_snapshot(self):
        first = parse_print({"mc_percent": 42}, new_snapshot())
        parse_print({"mc_percent": 99}, first)
        self.assertEqual(first["progress"], 42)

    def test_chamber_temp_nested_fallback(self):
        snap = parse_print({"device": {"ctc": {"info": {"temp": 31.5}}}}, new_snapshot())
        self.assertEqual(snap["chamber"], 31.5)

    def test_garbage_values_keep_the_fallback(self):
        prev = parse_print({"mc_percent": 42}, new_snapshot())
        snap = parse_print({"mc_percent": "n/a"}, prev)
        self.assertEqual(snap["progress"], 42)

    def test_alerts_only_updated_when_reported(self):
        raised = parse_print({"print_error": 0x0300_4001}, new_snapshot())
        self.assertTrue(raised["alert_active"])
        # A report with neither key must leave the banner alone.
        unchanged = parse_print({"mc_percent": 50}, raised)
        self.assertTrue(unchanged["alert_active"])
        # An explicit clear resets it.
        cleared = parse_print({"print_error": 0, "hms": []}, raised)
        self.assertFalse(cleared["alert_active"])

    def test_end_to_end_completion(self):
        """A print running -> finishing produces FINISH with usable placeholders."""
        running = parse_print({"gcode_state": "RUNNING", "mc_percent": 99,
                               "subtask_name": "benchy.3mf"}, new_snapshot())
        done = parse_print({"gcode_state": "FINISH", "mc_percent": 100}, running)
        self.assertEqual(triggers_fired(running, done), ["FINISH"])
        msg = substitute({"message": "$job done ($state_label)"},
                         placeholder_values(done))
        self.assertEqual(msg["message"], "benchy.3mf done (COMPLETE)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
