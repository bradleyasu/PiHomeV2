import json
import threading

from events.pihomeevent import PihomeEvent
from util.phlog import PIHOME_LOGGER


class MultiEvent(PihomeEvent):
    """
    The MultiEvent class is a composite event that can execute multiple events at once.  Keep in mind that the the multi event may return
    with a successful HTTP 200 status code even if one or more of the events it contains fails.  The 200 in this case means that the multi event
    was successully processed, not that all of the events it contains were successful.  The responses attribute of the response body will contain the
    responses of each of the events that were executed.

    An optional `delay` argument (in seconds) inserts a pause between each event execution.
    When a delay is specified, events run in a background thread.
    """
    type = "multi"
    def __init__(self, events, delay=0, **kwargs):
        super().__init__()
        self.events = events
        self.delay = int(delay) if delay else 0

    def execute(self):
        if not isinstance(self.events, list):
            return {
                "code": 400,
                "body": {"status": "error", "message": "events attribute must be a list, not {}".format(type(self.events))}
            }

        if self.delay > 0:
            thread = threading.Thread(target=self._execute_with_delay, daemon=True)
            thread.start()
            return {
                "code": 200,
                "body": {"status": "success", "message": "Multi action executing in background with {}s delay between events".format(self.delay)}
            }

        return self._execute_events()

    def _execute_events(self):
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

    def _execute_with_delay(self):
        from events.pihomeevent import PihomeEventFactory
        stop = threading.Event()
        for i, event in enumerate(self.events):
            try:
                e = PihomeEventFactory.create_event_from_dict(event)
                e.execute()
            except Exception as e:
                PIHOME_LOGGER.error("MultiEvent: failed to execute event {}: {}".format(i, e))
            if i < len(self.events) - 1:
                stop.wait(self.delay)


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "events": [event.to_json() for event in self.events],
            "delay": self.delay,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "events": self.type_def("list"),
            "delay": self.type_def("integer", False, "Delay in seconds between each event execution"),
        }