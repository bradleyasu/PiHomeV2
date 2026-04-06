import json
from events.pihomeevent import PihomeEvent


class RemoveHaReactEvent(PihomeEvent):
    """Remove a previously registered HA react listener by its ID.

    The listener is removed from memory and the persisted file is updated
    immediately, so it will not be re-loaded on the next PiHome restart.

    Webhook / task payload example
    ───────────────────────────────
    {
        "type": "remove_hareact",
        "id": "a1b2c3d4-e5f6-..."
    }

    The listener ID is returned in the response body of the original
    hareact event that registered it.
    """

    type = "remove_hareact"

    def __init__(self, id, **kwargs):
        super().__init__()
        self.listener_id = id

    def execute(self):
        from services.homeassistant.homeassistant import HOME_ASSISTANT

        removed = HOME_ASSISTANT.remove_react_listener(self.listener_id)

        if removed:
            return {
                "code": 200,
                "body": {
                    "status":      "success",
                    "message":     f"HA react listener {self.listener_id} removed",
                    "listener_id": self.listener_id,
                },
            }
        else:
            return {
                "code": 404,
                "body": {
                    "status":      "error",
                    "message":     f"HA react listener {self.listener_id} not found",
                    "listener_id": self.listener_id,
                },
            }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "id":   self.listener_id,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "id":   self.type_def("string", True, "ID of the HA react listener to remove"),
        }
