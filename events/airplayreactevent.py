import json
from events.pihomeevent import PihomeEvent


class AirPlayReactEvent(PihomeEvent):
    """Register a persistent AirPlay state-change listener.

    When AirPlay playback starts or stops (depending on the trigger),
    the supplied event is executed.

    The listener is persisted to disk so it survives PiHome restarts.

    Webhook / task payload example
    ───────────────────────────────
    {
        "type": "airplay_react",
        "trigger": "on_start",
        "event": {
            "type": "toast",
            "message": "AirPlay started!",
            "level": "info",
            "timeout": 5
        }
    }
    """

    type = "airplay_react"

    def __init__(self, trigger, event, **kwargs):
        super().__init__()
        self.trigger = trigger  # "on_start" or "on_stop"
        self.event   = event    # dict, executed via PihomeEventFactory

    def execute(self):
        from services.airplay.airplay import AIRPLAY, AirPlayReactListener

        if self.trigger not in ("on_start", "on_stop"):
            return {
                "code": 400,
                "body": {
                    "status":  "error",
                    "message": "trigger must be 'on_start' or 'on_stop'",
                },
            }

        listener = AirPlayReactListener(
            trigger = self.trigger,
            action  = self.event,
        )
        listener_id = AIRPLAY.add_react_listener(listener)

        return {
            "code": 200,
            "body": {
                "status":      "success",
                "message":     "AirPlay react listener registered",
                "listener_id": listener_id,
            },
        }

    def to_json(self):
        return json.dumps({
            "type":    self.type,
            "trigger": self.trigger,
            "event":   self.event,
        })

    def to_definition(self):
        return {
            "type":    self.type,
            "trigger": self.type_def("option", True, "When to fire: 'on_start' or 'on_stop'", ["on_start", "on_stop"]),
            "event":   self.type_def("event",  True, "PiHome event dict to execute when the listener fires"),
        }
