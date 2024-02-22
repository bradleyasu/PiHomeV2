import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent


class ToastEvent(PihomeEvent):
    def __init__(self, label, level = "info", timeout = 5, **kwargs):
        super().__init__()
        self.type = "toast"
        self.label = label
        self.level = level
        self.timeout = timeout

    def execute(self):
        pass


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "label": self.label,
            "level": self.level,
            "timeout": self.timeout
        })
