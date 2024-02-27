
import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent, PihomeEventFactory


class IntrospectionEvent(PihomeEvent):
    """
    The Introspection Event is a special event used to introspect all events in the system and return their definitions. This
    is implemented as an event to allow access to the event definitions through various interfaces such as the web interface.
    """
    type = "introspect"
    def __init__(self, event = None, **kwargs):
        """
        If an event is provided, the introspection event will return the definition of the provided event. If no event is
        provided, the introspection event will return the definitions of all events in the system.
        """
        super().__init__()
        self.event = event

    def execute(self):
        definitions = PihomeEventFactory.get_event_definitions()
        if self.event:
            # filter out definitions to match event == type
            definitions = list(filter(lambda x: x["type"] == self.event, definitions))
        return {
            "code": 200,
            "body": {
                "event_count": len(definitions),
                "definitions": definitions
            }
        }


    def to_json(self):
        return json.dumps({
            "type": self.type
        })

    def to_definition(self):
        return {
            "type": self.type,
            "event": self.type_def("string", False)
        }
