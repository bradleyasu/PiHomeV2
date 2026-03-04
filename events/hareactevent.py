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

    def to_definition(self):
        return {
            "type":      self.type,
            "entity_id": self.type_def("string", True,  "HA entity to watch, e.g. binary_sensor.front_door"),
            "state":     self.type_def("string", False, "State that triggers the action; omit to react to any change"),
            "action":    self.type_def("event",  True,  "PiHome event dict to execute when the listener fires"),
        }
