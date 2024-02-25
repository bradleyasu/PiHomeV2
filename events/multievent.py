import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent


class MultiEvent(PihomeEvent):
    type = "multi"
    def __init__(self, events, **kwargs):
        super().__init__()
        self.events = events

    def execute(self):
        if not isinstance(self.events, list):
            return {
                "code": 400,
                "body": {"status": "error", "message": "events attribute must be a list, not {}".format(type(self.events))}
            }
        responses = []
        from events.pihomeevent import PihomeEventFactory
        for event in self.events:
            try:
                e = PihomeEventFactory.create_event_from_dict(event)
                responses.append(e.execute())
            except Exception as e:
                responses.append({"status": "error", "message": "Failed to execute event", "error": str(e)})

        return {
            "code": 200,
            "body": {"status": "success", "message": "Multi action executed successfully",
                     "responses": responses}
        }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "events": [event.to_json() for event in self.events]
        })
