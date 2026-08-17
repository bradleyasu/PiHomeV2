"""Headless unit tests for util.rulestore (pure-logic + file persistence).

No Kivy, no GL context, no services. Firing is intercepted so nothing is
dispatched to a real event.

Run:  venv/bin/python -m unittest util.test_rulestore
"""

import json
import os
import shutil
import tempfile
import time
import unittest

from util import rulestore
from util.rulestore import (
    RULE_STORES, RuleStore, describe_event, format_age, substitute,
)


def _event(message="hi"):
    return {"type": "toast", "message": message}


class StoreTestCase(unittest.TestCase):
    """Base: a store in a temp dir, with dispatch captured instead of executed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "rules.json")
        self.dispatched = []
        self.store = self._make_store()

    def tearDown(self):
        RULE_STORES.pop("test", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_store(self, **kwargs):
        kwargs.setdefault("describe", lambda r: f"On {r.get('state')}")
        store = RuleStore("test", "Test", self.path, glyph="x", **kwargs)
        store._dispatch = lambda payload, rid: self.dispatched.append(payload)
        return store


class TestUpsert(StoreTestCase):

    def test_generates_an_id_when_omitted(self):
        r = self.store.upsert({"state": "FINISH", "event": _event()})
        self.assertEqual(r["code"], 200)
        self.assertTrue(r["body"]["id"])

    def test_same_id_updates_in_place(self):
        self.store.upsert({"id": "a", "state": "FINISH", "event": _event("one")})
        self.store.upsert({"id": "a", "state": "FAILED", "event": _event("two")})
        rules = self.store.list()["body"]["rules"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["state"], "FAILED")
        self.assertEqual(rules[0]["event"]["message"], "two")

    def test_update_preserves_fire_history(self):
        """Editing a rule must not reset its cooldown or its last-fired display."""
        self.store.upsert({"id": "a", "state": "FINISH", "event": _event()})
        self.store.fire(self.store.get("a"))
        fired_at = self.store.get("a")["last_fired"]
        self.assertIsNotNone(fired_at)
        self.store.upsert({"id": "a", "state": "FAILED", "event": _event()})
        self.assertEqual(self.store.get("a")["last_fired"], fired_at)

    def test_defaults_enabled_and_last_fired(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event()})
        rule = self.store.get("a")
        self.assertTrue(rule["enabled"])
        self.assertIsNone(rule["last_fired"])
        self.assertEqual(rule["cooldown"], 0)

    def test_rejects_missing_or_bad_event(self):
        self.assertEqual(self.store.upsert({"state": "X"})["code"], 400)
        self.assertEqual(self.store.upsert({"state": "X", "event": "nope"})["code"], 400)
        self.assertEqual(self.store.upsert({"state": "X", "event": {}})["code"], 400)

    def test_rejects_bad_cooldown(self):
        self.assertEqual(
            self.store.upsert({"state": "X", "event": _event(), "cooldown": "soon"})["code"], 400)
        self.assertEqual(
            self.store.upsert({"state": "X", "event": _event(), "cooldown": -5})["code"], 400)

    def test_custom_validate_hook(self):
        def validate(rule):
            return None if rule.get("state") else "'state' is required"
        self.assertEqual(self.store.upsert({"event": _event()}, validate=validate)["code"], 400)
        self.assertEqual(
            self.store.upsert({"state": "X", "event": _event()}, validate=validate)["code"], 200)

    def test_enabled_accepts_string_booleans(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "enabled": "0"})
        self.assertFalse(self.store.get("a")["enabled"])


class TestRemoveAndToggle(StoreTestCase):

    def setUp(self):
        super().setUp()
        self.store.upsert({"id": "a", "state": "X", "event": _event()})

    def test_remove_existing(self):
        self.assertEqual(self.store.remove("a")["code"], 200)
        self.assertEqual(self.store.list()["body"]["rules"], [])

    def test_remove_missing_is_404(self):
        """Standardized: deleting a rule that isn't there is a failure."""
        r = self.store.remove("nope")
        self.assertEqual(r["code"], 404)
        self.assertEqual(r["body"]["status"], "error")

    def test_remove_requires_id(self):
        self.assertEqual(self.store.remove("")["code"], 400)

    def test_set_enabled(self):
        self.assertEqual(self.store.set_enabled("a", False)["code"], 200)
        self.assertFalse(self.store.get("a")["enabled"])
        self.store.set_enabled("a", True)
        self.assertTrue(self.store.get("a")["enabled"])

    def test_set_enabled_missing_is_404(self):
        self.assertEqual(self.store.set_enabled("nope", False)["code"], 404)


class TestFiring(StoreTestCase):

    def test_fires_and_substitutes(self):
        self.store.upsert({"id": "a", "state": "FINISH",
                           "event": {"type": "toast", "message": "$job done"}})
        self.assertTrue(self.store.fire(self.store.get("a"), {"job": "benchy"}))
        self.assertEqual(self.dispatched[0]["message"], "benchy done")

    def test_fire_by_id_string(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event()})
        self.assertTrue(self.store.fire("a"))
        self.assertEqual(len(self.dispatched), 1)

    def test_disabled_rule_does_not_fire(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "enabled": False})
        self.assertFalse(self.store.fire(self.store.get("a")))
        self.assertEqual(self.dispatched, [])

    def test_force_overrides_disabled(self):
        """Test-fire from the Automations screen must work on a disabled rule."""
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "enabled": False})
        self.assertTrue(self.store.fire(self.store.get("a"), force=True))
        self.assertEqual(len(self.dispatched), 1)

    def test_cooldown_suppresses_second_fire(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "cooldown": 60})
        self.assertTrue(self.store.fire(self.store.get("a")))
        self.assertFalse(self.store.fire(self.store.get("a")))
        self.assertEqual(len(self.dispatched), 1)

    def test_force_overrides_cooldown(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "cooldown": 60})
        self.store.fire(self.store.get("a"))
        self.assertTrue(self.store.fire(self.store.get("a"), force=True))
        self.assertEqual(len(self.dispatched), 2)

    def test_expired_cooldown_allows_fire(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "cooldown": 1})
        self.store.fire(self.store.get("a"))
        self.store._rules["a"]["last_fired"] = time.time() - 5
        self.assertTrue(self.store.fire(self.store.get("a")))
        self.assertEqual(len(self.dispatched), 2)

    def test_fire_matching_only_hits_the_field(self):
        self.store.upsert({"id": "a", "state": "FINISH", "event": _event("a")})
        self.store.upsert({"id": "b", "state": "FINISH", "event": _event("b")})
        self.store.upsert({"id": "c", "state": "FAILED", "event": _event("c")})
        self.assertEqual(self.store.fire_matching("state", "FINISH"), 2)
        self.assertEqual(sorted(d["message"] for d in self.dispatched), ["a", "b"])

    def test_fire_matching_skips_disabled(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "enabled": False})
        self.store.upsert({"id": "b", "state": "X", "event": _event()})
        self.assertEqual(self.store.fire_matching("state", "X"), 1)

    def test_fire_records_last_fired(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event()})
        self.store.fire(self.store.get("a"))
        self.assertIsNotNone(self.store.get("a")["last_fired"])

    def test_rule_without_event_does_not_fire(self):
        self.assertFalse(self.store.fire({"id": "x", "enabled": True}))


class TestFireAndWait(StoreTestCase):
    """The synchronous path, used where the caller reports what the action did."""

    def setUp(self):
        super().setUp()
        # Intercept the factory rather than _dispatch — fire_and_wait executes inline.
        import events.pihomeevent as pe
        self._real = pe.PihomeEventFactory.create_event_from_dict

        class _Fake:
            def __init__(self, payload):
                self.payload = payload

            def execute_safe(self, timeout=10):
                return {"code": 200, "body": {"status": "success",
                                              "echo": self.payload.get("message")}}

        pe.PihomeEventFactory.create_event_from_dict = staticmethod(_Fake)
        self._pe = pe

    def tearDown(self):
        self._pe.PihomeEventFactory.create_event_from_dict = self._real
        super().tearDown()

    def test_returns_the_actions_response(self):
        self.store.upsert({"id": "a", "state": "X",
                           "event": {"type": "toast", "message": "pressed $1"}})
        fired, response = self.store.fire_and_wait(self.store.get("a"), {"1": "80"})
        self.assertTrue(fired)
        self.assertEqual(response["body"]["echo"], "pressed 80")

    def test_disabled_returns_not_fired_and_no_response(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "enabled": False})
        self.assertEqual(self.store.fire_and_wait(self.store.get("a")), (False, None))

    def test_records_last_fired(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event()})
        self.store.fire_and_wait(self.store.get("a"))
        self.assertIsNotNone(self.store.get("a")["last_fired"])

    def test_unknown_id(self):
        self.assertEqual(self.store.fire_and_wait("nope"), (False, None))


class TestPersistence(StoreTestCase):

    def test_survives_reload(self):
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "cooldown": 30})
        self.store.set_enabled("a", False)
        self.store.fire(self.store.get("a"), force=True)
        fired_at = self.store.get("a")["last_fired"]

        reopened = self._make_store()
        rule = reopened.get("a")
        self.assertFalse(rule["enabled"])
        self.assertEqual(rule["cooldown"], 30)
        self.assertEqual(rule["last_fired"], fired_at)

    def test_cooldown_survives_restart(self):
        """The bug this fixes: BambuLab kept last_fired in memory only."""
        self.store.upsert({"id": "a", "state": "X", "event": _event(), "cooldown": 3600})
        self.store.fire(self.store.get("a"))
        reopened = self._make_store()
        self.assertFalse(reopened.fire(reopened.get("a")))

    def test_reads_a_legacy_file_without_the_new_fields(self):
        """Existing rule files predate enabled/last_fired — no migration needed."""
        with open(self.path, "w") as f:
            json.dump({"a": {"id": "a", "state": "X", "event": _event()}}, f)
        store = self._make_store()
        rule = store.get("a")
        self.assertTrue(rule["enabled"])
        self.assertIsNone(rule["last_fired"])

    def test_corrupt_file_is_not_clobbered(self):
        with open(self.path, "w") as f:
            f.write("{ this is not json")
        store = self._make_store()
        self.assertEqual(store.list()["body"]["rules"], [])
        store._save()                       # would wipe the file without the guard
        with open(self.path) as f:
            self.assertIn("not json", f.read())

    def test_writing_after_a_successful_empty_load_is_allowed(self):
        store = self._make_store()          # no file yet -> loaded == True
        store.upsert({"id": "a", "state": "X", "event": _event()})
        store.remove("a")
        with open(self.path) as f:
            self.assertEqual(json.load(f), {})

    def test_creates_missing_directory(self):
        nested = os.path.join(self.tmp, "deep", "dir", "rules.json")
        store = RuleStore("nested", "Nested", nested, register=False)
        store.upsert({"id": "a", "event": _event()})
        self.assertTrue(os.path.exists(nested))


class TestCompositeKey(StoreTestCase):
    """BLE keys bindings by device|command rather than by id."""

    def _make_store(self, **kwargs):
        kwargs["key_fn"] = lambda r: f"{r.get('device') or '*'}|{r.get('command')}"
        return super()._make_store(**kwargs)

    def test_same_command_on_two_devices_coexists(self):
        self.store.upsert({"id": "1", "command": "a", "device": "AA", "event": _event()})
        self.store.upsert({"id": "2", "command": "a", "device": "BB", "event": _event()})
        self.assertEqual(len(self.store.list()["body"]["rules"]), 2)

    def test_same_key_replaces(self):
        self.store.upsert({"id": "1", "command": "a", "device": "AA", "event": _event("x")})
        self.store.upsert({"id": "2", "command": "a", "device": "AA", "event": _event("y")})
        rules = self.store.list()["body"]["rules"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["event"]["message"], "y")

    def test_remove_and_get_still_work_by_id(self):
        self.store.upsert({"id": "1", "command": "a", "device": "AA", "event": _event()})
        self.assertIsNotNone(self.store.get("1"))
        self.assertEqual(self.store.remove("1")["code"], 200)

    def test_remove_works_by_composite_key_too(self):
        self.store.upsert({"id": "1", "command": "a", "device": "AA", "event": _event()})
        self.assertEqual(self.store.remove("AA|a")["code"], 200)


class TestRegistry(unittest.TestCase):

    def tearDown(self):
        RULE_STORES.pop("reg", None)

    def test_construction_registers(self):
        store = RuleStore("reg", "Reg", os.path.join(tempfile.mkdtemp(), "r.json"))
        self.assertIs(RULE_STORES["reg"], store)

    def test_register_false_stays_out(self):
        RuleStore("reg", "Reg", os.path.join(tempfile.mkdtemp(), "r.json"), register=False)
        self.assertNotIn("reg", RULE_STORES)


class TestSubstitute(unittest.TestCase):

    def test_named(self):
        out = substitute({"m": "$job at $progress%"}, {"job": "benchy", "progress": 42})
        self.assertEqual(out["m"], "benchy at 42%")

    def test_positional_dollar_one_still_works(self):
        """BLE bindings and shell events use $1 — that must keep working."""
        self.assertEqual(substitute({"level": "$1"}, {"1": 80})["level"], "80")

    def test_longer_keys_win(self):
        out = substitute({"m": "$layer/$layer_total"}, {"layer": 10, "layer_total": 250})
        self.assertEqual(out["m"], "10/250")

    def test_recurses_and_leaves_non_strings(self):
        out = substitute(
            {"type": "multi", "timeout": 5, "events": [{"m": "$state"}]}, {"state": "X"})
        self.assertEqual(out["events"][0]["m"], "X")
        self.assertEqual(out["timeout"], 5)

    def test_does_not_mutate_input(self):
        event = {"m": "$state"}
        substitute(event, {"state": "X"})
        self.assertEqual(event["m"], "$state")

    def test_none_value_becomes_empty_string(self):
        self.assertEqual(substitute({"m": "[$v]"}, {"v": None})["m"], "[]")

    def test_no_values_is_a_passthrough_copy(self):
        self.assertEqual(substitute({"m": "$state"}, None)["m"], "$state")


class TestDescribeEvent(unittest.TestCase):

    def test_message(self):
        self.assertEqual(describe_event({"type": "toast", "message": "hi"}), "toast: hi")

    def test_prefers_message_over_title(self):
        self.assertEqual(
            describe_event({"type": "n", "message": "m", "title": "t"}), "n: m")

    def test_falls_back_to_title(self):
        self.assertEqual(
            describe_event({"type": "notification", "title": "Done"}), "notification: Done")

    def test_nested_multi(self):
        self.assertEqual(
            describe_event({"type": "multi", "events": [1, 2, 3]}), "multi (3 events)")

    def test_bare_type(self):
        self.assertEqual(describe_event({"type": "reboot"}), "reboot")

    def test_non_dict(self):
        self.assertEqual(describe_event(None), "(no action)")

    def test_blank_summary_field_is_skipped(self):
        self.assertEqual(describe_event({"type": "x", "message": "   "}), "x")


class TestFormatAge(unittest.TestCase):

    def test_never(self):
        self.assertEqual(format_age(None), "never fired")

    def test_relative(self):
        now = 1_000_000
        self.assertEqual(format_age(now - 10, now), "just now")
        self.assertEqual(format_age(now - 300, now), "5m ago")
        self.assertEqual(format_age(now - 7200, now), "2h ago")
        self.assertEqual(format_age(now - 3 * 86400, now), "3d ago")


if __name__ == "__main__":
    unittest.main(verbosity=2)
