"""Shared persistence and firing for trigger -> event rules.

PiHome grew five near-identical "rule store" implementations — BLE command
bindings, Emporia power-threshold alerts, BambuLab printer-state alerts, AirPlay
and Home Assistant react listeners. Each one hand-rolled the same JSON
persistence, the same add/list/remove response shapes (which had already drifted
apart), and its own ``Clock.schedule_once`` + ``execute()`` dance to fire the
bound event on the main thread — a footgun whose failure mode is a silent
no-fire.

This module is the one implementation of all of that:

  * keyed JSON persistence under ``cache/``, with a clobber guard
  * upsert / list / remove / set_enabled with a single consistent response shape
  * per-rule ``enabled`` flag and ``last_fired`` timestamp
  * cooldown suppression
  * placeholder substitution (named ``$state`` and positional ``$1``)
  * correct main-thread dispatch of the bound event

A service creates one ``RuleStore`` and keeps its own trigger evaluation — the
part that is genuinely different between a power threshold, a printer state, and
a BLE token.

Constructing a store registers it in :data:`RULE_STORES`, which is what the
Automations screen enumerates. Registration happens on import, so a screen whose
directory has been removed simply never registers and quietly disappears from the
UI — no screen has to import another screen's service.

Kivy is imported lazily (inside ``fire``) so this module stays unit-testable
headlessly.
"""

import copy
import json
import os
import threading
import time
import uuid

from util.phlog import PIHOME_LOGGER

# key -> RuleStore / adapter. Enumerated by the Automations screen and the
# automations_list event. Insertion-ordered so the UI is stable across restarts.
RULE_STORES = {}


def register_store(store):
    """Add a store (or a read-only adapter) to the global registry."""
    key = getattr(store, "key", None)
    if not key:
        PIHOME_LOGGER.error("RuleStore: refusing to register a store with no key")
        return store
    if key in RULE_STORES and RULE_STORES[key] is not store:
        PIHOME_LOGGER.warn(f"RuleStore: replacing already-registered store '{key}'")
    RULE_STORES[key] = store
    return store


# ── Placeholder substitution ───────────────────────────────────────────────────

def substitute(event, values):
    """Deep-copy ``event`` and replace every ``$name`` placeholder in it.

    Accepts both conventions already in the codebase: named keys (BambuLab's
    ``$state`` / ``$job``) and positional ones (``$1``, used by BLE bindings and
    events/shellevent.py) — a positional caller just passes ``{"1": value}``.

    Longer keys are replaced first so ``$layer_total`` is not clobbered by
    ``$layer``.
    """
    payload = copy.deepcopy(event)
    if not values:
        return payload
    ordered = sorted(
        ((str(k), "" if v is None else str(v)) for k, v in values.items()),
        key=lambda kv: len(kv[0]), reverse=True,
    )
    return _replace(payload, ordered)


def _replace(node, ordered):
    if isinstance(node, dict):
        return {k: _replace(v, ordered) for k, v in node.items()}
    if isinstance(node, list):
        return [_replace(v, ordered) for v in node]
    if isinstance(node, str):
        text = node
        for name, value in ordered:
            token = "$" + name
            if token in text:
                text = text.replace(token, value)
        return text
    return node


# ── Human-readable rendering ───────────────────────────────────────────────────

# Fields worth showing after the event type, in order of preference.
_SUMMARY_KEYS = ("message", "title", "name", "text", "label", "command", "entity_id", "id")


def describe_event(event):
    """Render a stored event dict as a short human-readable action string.

    Used for the Automations row subtitle and the automations_list response, so a
    rule reads as "toast: Print done" rather than a blob of JSON.
    """
    if not isinstance(event, dict):
        return "(no action)"
    etype = event.get("type") or "?"

    nested = event.get("events")
    if isinstance(nested, list) and nested:
        return f"{etype} ({len(nested)} events)"

    for key in _SUMMARY_KEYS:
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return f"{etype}: {value.strip()}"
    return str(etype)


def format_age(ts, now=None):
    """Relative 'when did this last fire' label. Mirrors the notification centre."""
    if not ts:
        return "never fired"
    delta = (now if now is not None else time.time()) - ts
    if delta < 0:
        return "just now"
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


# ── The store ──────────────────────────────────────────────────────────────────

def _ok(message, **extra):
    body = {"status": "success", "message": message}
    body.update(extra)
    return {"code": 200, "body": body}


def _err(message, code=400, **extra):
    body = {"status": "error", "message": message}
    body.update(extra)
    return {"code": code, "body": body}


class RuleStore:
    """Persistent collection of trigger -> event rules for one service."""

    # Adapters set this False; a real store always supports enable/disable.
    supports_enable = True
    supports_fire = True

    def __init__(self, key, label, path, glyph="", describe=None,
                 key_fn=None, create_event=None, register=True):
        """
        key          -- stable identifier, e.g. "bambulab"
        label        -- display name for the Automations section header
        path         -- JSON file under cache/
        glyph        -- MaterialIcons codepoint shown on each row
        describe     -- describe(rule) -> str, the human text for the TRIGGER
        key_fn       -- key_fn(rule) -> str, defaults to rule["id"]. BLE uses a
                        composite "device|command" key instead of an id.
        create_event -- the PiHome event type that creates a rule in this store
                        (e.g. "bambulab_state_alert"). Surfaced to the user by the
                        Automations screen's empty state and by automations_list,
                        so they can see exactly what to send. Always set it.
        """
        self.key = key
        self.label = label
        self.path = path
        self.glyph = glyph
        self.create_event = create_event
        self._describe = describe
        self._key_fn = key_fn or (lambda rule: str(rule.get("id") or ""))

        self._lock = threading.RLock()
        self._loaded = False        # guards against clobbering an unread file
        self._rules = self._load()

        if register:
            register_store(self)

    # ── Persistence ──

    def _load(self):
        """Read the store, defaulting in fields added after a file was written."""
        if not os.path.exists(self.path):
            # Nothing to lose — future writes are safe.
            self._loaded = True
            return {}
        try:
            with open(self.path) as f:
                raw = json.load(f) or {}
        except Exception as e:
            # Leave _loaded False so a corrupt file is not overwritten with {}.
            PIHOME_LOGGER.error(f"RuleStore[{self.key}]: failed to read {self.path}: {e}")
            return {}

        rules = {}
        for rkey, rule in (raw.items() if isinstance(raw, dict) else []):
            if not isinstance(rule, dict):
                continue
            rules[rkey] = self._normalize(rule)
        self._loaded = True
        return rules

    def _save(self):
        """Persist. Refuses to write an empty store that was never loaded."""
        if not self._rules and not self._loaded:
            PIHOME_LOGGER.warn(
                f"RuleStore[{self.key}]: refusing to overwrite {self.path} — "
                "nothing loaded and the in-memory store is empty"
            )
            return
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self._rules, f, indent=2)
        except Exception as e:
            PIHOME_LOGGER.error(f"RuleStore[{self.key}]: failed to write {self.path}: {e}")

    @staticmethod
    def _normalize(rule):
        """Default in fields added after older files were written."""
        rule = dict(rule)
        rule.setdefault("enabled", True)
        rule.setdefault("last_fired", None)
        rule.setdefault("cooldown", 0)
        return rule

    def reload(self):
        """Re-read from disk. Used by tests and by anything editing the file."""
        with self._lock:
            self._loaded = False
            self._rules = self._load()

    # ── CRUD ──

    def upsert(self, rule, validate=None):
        """Create or update a rule.

        ``id`` is optional — one is generated when omitted, so a caller can
        register a rule with nothing but a trigger and an action. Resending the
        same id updates in place.

        ``validate(rule) -> error_string_or_None`` lets the owning service apply
        its own field checks without reimplementing the response shape.
        """
        if not isinstance(rule, dict):
            return _err("rule must be an object")

        event = rule.get("event")
        if not isinstance(event, dict):
            return _err("'event' must be a nested event object")
        if not event.get("type"):
            return _err("'event' must contain a 'type'")

        try:
            cooldown = float(rule.get("cooldown") or 0)
        except (TypeError, ValueError):
            return _err("'cooldown' must be a number of seconds")
        if cooldown < 0:
            return _err("'cooldown' must not be negative")

        stored = self._normalize(rule)
        stored["id"] = str(rule.get("id") or "").strip() or str(uuid.uuid4())
        stored["cooldown"] = cooldown
        stored["enabled"] = _as_bool(rule.get("enabled", True))

        if validate is not None:
            error = validate(stored)
            if error:
                return _err(error)

        rkey = self._key_fn(stored)
        if not rkey:
            return _err("rule has no usable key")

        with self._lock:
            previous = self._rules.get(rkey)
            # Preserve fire history across an update so editing a rule doesn't
            # reset its cooldown or make it look like it never ran.
            if previous:
                stored["last_fired"] = previous.get("last_fired")
            self._rules[rkey] = stored
            self._save()

        return _ok(f"{self.label} rule '{stored['id']}' saved",
                   id=stored["id"], rule=stored)

    def list(self):
        with self._lock:
            rules = [dict(r) for r in self._rules.values()]
        return _ok(f"{len(rules)} rule(s)", rules=rules)

    def get(self, rid):
        """Look up by id (or by store key, for composite-keyed stores)."""
        with self._lock:
            rule = self._rules.get(rid)
            if rule is not None:
                return dict(rule)
            for candidate in self._rules.values():
                if candidate.get("id") == rid:
                    return dict(candidate)
        return None

    def remove(self, rid):
        rid = str(rid or "").strip()
        if not rid:
            return _err("'id' is required")
        with self._lock:
            rkey = self._resolve_key(rid)
            if rkey is None:
                return _err(f"{self.label} rule '{rid}' not found", code=404, id=rid)
            self._rules.pop(rkey, None)
            self._save()
        return _ok(f"{self.label} rule '{rid}' removed", id=rid)

    def set_enabled(self, rid, enabled):
        rid = str(rid or "").strip()
        if not rid:
            return _err("'id' is required")
        flag = _as_bool(enabled)
        with self._lock:
            rkey = self._resolve_key(rid)
            if rkey is None:
                return _err(f"{self.label} rule '{rid}' not found", code=404, id=rid)
            self._rules[rkey]["enabled"] = flag
            self._save()
            rule = dict(self._rules[rkey])
        state = "enabled" if flag else "disabled"
        return _ok(f"{self.label} rule '{rid}' {state}", id=rid, rule=rule)

    def _resolve_key(self, rid):
        """Map a user-supplied id onto the internal storage key. Caller holds the lock."""
        if rid in self._rules:
            return rid
        for rkey, rule in self._rules.items():
            if rule.get("id") == rid:
                return rkey
        return None

    # ── Firing ──

    def fire(self, rule, values=None, force=False):
        """Fire one rule's bound event. Returns True if it was dispatched.

        Skips disabled rules and rules still inside their cooldown, unless
        ``force`` (used by the Automations screen's test-fire, which should work
        regardless). Safe to call from any thread — the event is marshalled onto
        the Kivy main thread, since actions almost always touch the UI.
        """
        if isinstance(rule, str):
            rule = self.get(rule)
        if not isinstance(rule, dict):
            return False

        rid = rule.get("id")
        if not self._may_fire(rule, force):
            return False

        event = rule.get("event")
        if not isinstance(event, dict):
            PIHOME_LOGGER.error(f"{self.label} rule '{rid}': no valid 'event' to fire")
            return False

        self._touch(rule)
        payload = substitute(event, values)
        PIHOME_LOGGER.info(f"{self.label} rule '{rid}' fired -> {payload.get('type')}")
        self._dispatch(payload, rid)
        return True

    def fire_matching(self, field, value, values=None, force=False):
        """Fire every rule whose ``field`` equals ``value``. Returns the count."""
        with self._lock:
            candidates = [dict(r) for r in self._rules.values() if r.get(field) == value]
        return sum(1 for rule in candidates if self.fire(rule, values, force=force))

    def fire_and_wait(self, rule, values=None, force=False, timeout=10):
        """Like :meth:`fire`, but block for the action's response and return it.

        Returns ``(fired, response)``. Callers that report what an action did —
        e.g. a manual "run this binding now" over HTTP — need the nested event's
        result, which the fire-and-forget path cannot give them. Safe on any
        thread: execute_safe runs inline when already on the main one.
        """
        if isinstance(rule, str):
            rule = self.get(rule)
        if not isinstance(rule, dict):
            return False, None
        if not self._may_fire(rule, force):
            return False, None

        event = rule.get("event")
        if not isinstance(event, dict):
            PIHOME_LOGGER.error(f"{self.label} rule '{rule.get('id')}': no valid 'event'")
            return False, None

        self._touch(rule)
        payload = substitute(event, values)
        PIHOME_LOGGER.info(
            f"{self.label} rule '{rule.get('id')}' fired -> {payload.get('type')}")
        try:
            from events.pihomeevent import PihomeEventFactory
            return True, PihomeEventFactory.create_event_from_dict(payload).execute_safe(
                timeout=timeout)
        except Exception as e:
            PIHOME_LOGGER.error(f"{self.label} rule '{rule.get('id')}': action failed: {e}")
            return True, None

    def _may_fire(self, rule, force):
        """Enabled + cooldown gate, shared by fire() and fire_and_wait()."""
        if force:
            return True
        rid = rule.get("id")
        if not rule.get("enabled", True):
            PIHOME_LOGGER.info(f"{self.label} rule '{rid}': skipped (disabled)")
            return False
        cooldown = rule.get("cooldown") or 0
        last = rule.get("last_fired")
        if cooldown and last and (time.time() - last) < cooldown:
            PIHOME_LOGGER.info(
                f"{self.label} rule '{rid}': suppressed by cooldown ({cooldown}s)")
            return False
        return True

    def _touch(self, rule):
        """Record that a rule fired, persisting so cooldowns survive a restart."""
        now = time.time()
        rule["last_fired"] = now
        with self._lock:
            rkey = self._resolve_key(rule.get("id") or "")
            if rkey is None:
                return
            self._rules[rkey]["last_fired"] = now
            self._save()

    def _dispatch(self, payload, rid):
        """Run the bound event on the Kivy main thread."""
        from util.helpers import run_on_main_thread_async

        def _do():
            try:
                # Imported lazily to avoid a circular import at module load.
                from events.pihomeevent import PihomeEventFactory
                PihomeEventFactory.create_event_from_dict(payload).execute()
            except Exception as e:
                PIHOME_LOGGER.error(f"{self.label} rule '{rid}': action failed: {e}")

        run_on_main_thread_async(_do)

    # ── Presentation (used by the Automations screen) ──

    def describe(self, rule):
        """Human-readable text for this rule's TRIGGER."""
        if self._describe is not None:
            try:
                return self._describe(rule)
            except Exception as e:
                PIHOME_LOGGER.error(f"RuleStore[{self.key}]: describe failed: {e}")
        return rule.get("id", "")

    def describe_action(self, rule):
        return describe_event(rule.get("event"))


def _as_bool(value):
    """Config and JSON both hand us booleans as strings often enough to matter."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)
