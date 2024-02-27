import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent


class TimerEvent(PihomeEvent):
    type = "timer"
    def __init__(self, label, duration, on_complete = None, **kwargs):
        super().__init__()
        self.label = label
        self.duration = duration
        self.on_complete = on_complete

    def execute(self):
        TIMER_DRAWER.create_timer(self.duration, self.label, self.on_complete)
        return {
            "code": 200,
            "body": {"status": "success", "message": "Timer started"}
        }


    def __str__(self) -> str:
        return "TimerEvent: {} - {}".format(self.label, self.duration)

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "label": self.label,
            "duration": self.duration
        })

    def to_definition(self):
        return {
            "type": self.type,
            "label": self.type_def("string"),
            "duration": self.type_def("integer"),
            "on_complete": self.type_def("event", False)
        }