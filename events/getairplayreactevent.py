import json

from events.pihomeevent import PihomeEvent


class GetAirPlayReactEvent(PihomeEvent):
    type = "get_airplay_react"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        from services.airplay.airplay import AIRPLAY

        listeners = {l.id: {"trigger": l.trigger, "action": l.action} for l in AIRPLAY.react_listeners}
        return {
            "code": 200,
            "body": {"status": "success", "count": len(listeners), "listeners": listeners}
        }

    def to_json(self):
        return json.dumps({"type": self.type})

    def to_definition(self):
        return {
            "type": self.type,
        }
