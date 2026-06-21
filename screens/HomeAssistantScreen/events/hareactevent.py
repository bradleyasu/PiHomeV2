import json
from events.pihomeevent import PihomeEvent


class HaReactEvent(PihomeEvent):
    """Register a persistent Home Assistant state-change listener.

    When the watched entity enters the specified state (or changes at all if
    no state is provided), the supplied action event is executed.

    The listener is persisted to disk so it survives PiHome restarts.

    Webhook / task payload example
    ───────────────────────────────
    {
        "type": "hareact",
        "entity_id": "binary_sensor.front_door",
        "state": "on",
        "action": {
            "type": "alert",
            "title": "Front Door",
            "message": "The front door was opened.",
            "timeout": 10,
            "level": 1
        }
    }

    Omit "state" to react to any state change on the entity.
    """

    type = "hareact"

    def __init__(self, entity_id, action, state=None, **kwargs):
        super().__init__()
        self.entity_id = entity_id
        self.state     = state   # None → fire on any state change
        self.action    = action  # dict, executed via PihomeEventFactory

    def execute(self):
        from services.homeassistant.homeassistant import HOME_ASSISTANT, HaReactListener

        listener = HaReactListener(
            entity_id = self.entity_id,
            action    = self.action,
            state     = self.state,
        )
        listener_id = HOME_ASSISTANT.add_react_listener(listener)

        return {
            "code": 200,
            "body": {
                "status":      "success",
                "message":     "HA react listener registered",
                "listener_id": listener_id,
            },
        }

    def to_json(self):
        return json.dumps({
            "type":      self.type,
            "entity_id": self.entity_id,
            "state":     self.state,
            "action":    self.action,
        })

    def _entity_options(self):
        """Build an {entity_id: friendly_name} map from Home Assistant's cached
        states, sorted by the human-readable label.

        The event-builder UI renders a dict-valued `options` field as a Select
        where the dict key is the submitted value (entity_id) and the dict value
        is the displayed label (friendly name).  Returns an empty dict if HA has
        no states available (e.g. not configured / not yet connected)."""
        from services.homeassistant.homeassistant import HOME_ASSISTANT

        states = HOME_ASSISTANT.current_states or {}
        # If the cache is empty but HA is configured, try a one-off live fetch
        # so the dropdown is populated even right after startup.
        if not states and getattr(HOME_ASSISTANT, "ha_is_available", False):
            try:
                states = HOME_ASSISTANT.get_all_states() or {}
            except Exception:
                states = {}

        options = {}
        for entity_id, st in states.items():
            label = entity_id
            if isinstance(st, dict):
                label = st.get("attributes", {}).get("friendly_name") or entity_id
            options[entity_id] = label

        # Sort by label (case-insensitive) for a usable dropdown.
        return dict(sorted(options.items(), key=lambda kv: kv[1].lower()))

    def to_definition(self):
        entity_options = self._entity_options()
        if entity_options:
            entity_field = self.type_def(
                "option", True,
                "HA entity to watch", entity_options,
            )
        else:
            # Fall back to free-text entry when no entities are cached, so the
            # event can still be built while HA is offline.
            entity_field = self.type_def(
                "string", True,
                "HA entity to watch, e.g. binary_sensor.front_door",
            )

        return {
            "type":      self.type,
            "entity_id": entity_field,
            "state":     self.type_def("string", False, "State that triggers the action; omit to react to any change"),
            "action":    self.type_def("event",  True,  "PiHome event dict to execute when the listener fires"),
        }
