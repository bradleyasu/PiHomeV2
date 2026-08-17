"""Read-only rule-store adapters for the two legacy react-listener services.

AirPlay and Home Assistant predate :mod:`util.rulestore`: they keep their
listeners as objects in ``airplay_listeners.pihome`` / ``ha_listeners.pihome`` in
the project root, with their own serialization and their own add/remove events.
Rather than rewrite two working subsystems (and migrate live user data), these
adapters expose them through the same surface the Automations screen consumes, so
their listeners show up alongside everything else.

They deliberately support only *list*, *delete* and *test-fire*:

  * ``supports_enable = False`` — the underlying objects have no enabled flag, so
    the Automations row hides its toggle rather than pretending.
  * there is no ``last_fired`` — those services never recorded one.

Each adapter imports its service lazily inside a ``try``. A service that isn't
installed, isn't configured, or failed to start simply doesn't register, and the
screen shows one less section.
"""

from util.phlog import PIHOME_LOGGER
from util.rulestore import describe_event, register_store, substitute


class _ReactListenerAdapter:
    """Common shape over AirPlay's and HA's list-of-objects listener stores."""

    supports_enable = False
    supports_fire = True

    def __init__(self, key, label, glyph, describe, create_event=None):
        self.key = key
        self.label = label
        self.glyph = glyph
        self.create_event = create_event
        self._describe = describe

    # ── Subclass hooks ──

    def _listeners(self):
        """Return the live list of listener objects."""
        raise NotImplementedError

    def _delete(self, rid):
        """Remove by id; return True if something was removed."""
        raise NotImplementedError

    @staticmethod
    def _action(listener):
        """The nested event dict this listener fires."""
        raise NotImplementedError

    # ── RuleStore-compatible surface ──

    def _as_rule(self, listener):
        return {
            "id": getattr(listener, "id", ""),
            "event": self._action(listener),
            "enabled": True,
            "last_fired": None,
            "cooldown": 0,
        }

    def list(self):
        try:
            rules = [self._as_rule(l) for l in self._listeners()]
        except Exception as e:
            PIHOME_LOGGER.error(f"RuleAdapter[{self.key}]: list failed: {e}")
            rules = []
        return {"code": 200, "body": {"status": "success", "rules": rules}}

    def get(self, rid):
        for rule in self.list()["body"]["rules"]:
            if rule["id"] == rid:
                return rule
        return None

    def remove(self, rid):
        rid = str(rid or "").strip()
        try:
            removed = self._delete(rid)
        except Exception as e:
            PIHOME_LOGGER.error(f"RuleAdapter[{self.key}]: remove failed: {e}")
            return {"code": 500, "body": {"status": "error", "message": str(e)}}
        if not removed:
            return {"code": 404, "body": {
                "status": "error", "message": f"{self.label} rule '{rid}' not found"}}
        return {"code": 200, "body": {
            "status": "success", "message": f"{self.label} rule '{rid}' removed"}}

    def set_enabled(self, rid, enabled):
        return {"code": 400, "body": {
            "status": "error",
            "message": f"{self.label} rules cannot be enabled/disabled"}}

    def fire(self, rule, values=None, force=False):
        """Test-fire this listener's action on the main thread."""
        if isinstance(rule, str):
            rule = self.get(rule)
        if not isinstance(rule, dict):
            return False
        event = rule.get("event")
        if not isinstance(event, dict):
            PIHOME_LOGGER.error(f"{self.label} rule '{rule.get('id')}': no valid event")
            return False

        from util.helpers import run_on_main_thread_async
        payload = substitute(event, values)

        def _do():
            try:
                from events.pihomeevent import PihomeEventFactory
                PihomeEventFactory.create_event_from_dict(payload).execute()
            except Exception as e:
                PIHOME_LOGGER.error(
                    f"{self.label} rule '{rule.get('id')}': action failed: {e}")

        PIHOME_LOGGER.info(f"{self.label} rule '{rule.get('id')}' fired (manual)")
        run_on_main_thread_async(_do)
        return True

    # ── Presentation ──

    def describe(self, rule):
        try:
            return self._describe(rule)
        except Exception:
            return rule.get("id", "")

    def describe_action(self, rule):
        return describe_event(rule.get("event"))


class _AirPlayAdapter(_ReactListenerAdapter):

    def __init__(self):
        super().__init__("airplay", "AirPlay", "", self._describe_rule,
                         create_event="airplay_react")

    @staticmethod
    def _service():
        from services.airplay.airplay import AIRPLAY
        return AIRPLAY

    def _listeners(self):
        return list(self._service().react_listeners)

    def _delete(self, rid):
        return bool(self._service().remove_react_listener(rid))

    @staticmethod
    def _action(listener):
        return getattr(listener, "action", None)

    def _as_rule(self, listener):
        rule = super()._as_rule(listener)
        rule["trigger"] = getattr(listener, "trigger", "")
        return rule

    @staticmethod
    def _describe_rule(rule):
        trigger = rule.get("trigger", "")
        readable = {"on_start": "playback starts", "on_stop": "playback stops"}
        return "AirPlay " + readable.get(trigger, trigger or "changes")


class _HomeAssistantAdapter(_ReactListenerAdapter):

    def __init__(self):
        super().__init__("homeassistant", "Home Assistant", "", self._describe_rule,
                         create_event="hareact")

    @staticmethod
    def _service():
        from services.homeassistant.homeassistant import HOME_ASSISTANT
        return HOME_ASSISTANT

    def _listeners(self):
        return list(self._service().ha_react_listeners)

    def _delete(self, rid):
        return bool(self._service().remove_react_listener(rid))

    @staticmethod
    def _action(listener):
        return getattr(listener, "action", None)

    def _as_rule(self, listener):
        rule = super()._as_rule(listener)
        rule["entity_id"] = getattr(listener, "entity_id", "")
        rule["state"] = getattr(listener, "state", None)
        return rule

    @staticmethod
    def _describe_rule(rule):
        entity = rule.get("entity_id", "?")
        state = rule.get("state")
        return f"{entity} becomes '{state}'" if state else f"{entity} changes"


def register_adapters():
    """Register every legacy adapter whose service is importable.

    Called by the Automations screen on entry, so a service that starts late
    still shows up. Already-registered adapters are left alone, which keeps this
    quiet and idempotent across repeated visits to the screen.
    """
    from util.rulestore import RULE_STORES

    for factory in (_AirPlayAdapter, _HomeAssistantAdapter):
        try:
            adapter = factory()
            if adapter.key in RULE_STORES:
                continue
            adapter._listeners()          # probe: fails fast if the service is absent
            register_store(adapter)
        except Exception as e:
            PIHOME_LOGGER.info(
                f"RuleAdapter: {factory.__name__} unavailable, skipping ({e})")
