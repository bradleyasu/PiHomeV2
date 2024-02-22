import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent


class TimerEvent(PihomeEvent):
    def __init__(self, label, duration, **kwargs):
        super().__init__()
        self.type = "timer"
        self.label = label
        self.duration = duration

    def execute(self):
        TIMER_DRAWER.create_timer(self.duration, self.label)
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
