import json
from events.pihomeevent import PihomeEvent

class MultiEvent(PihomeEvent):
    """
    The MultiEvent class is a composite event that can execute multiple events at once.  Keep in mind that the the multi event may return
    with a successful HTTP 200 status code even if one or more of the events it contains fails.  The 200 in this case means that the multi event
    was successully processed, not that all of the events it contains were successful.  The responses attribute of the response body will contain the
    responses of each of the events that were executed.
    """
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


    def to_definition(self):
        return {
            "type": self.type,
            "events": self.type_def("list")
        }