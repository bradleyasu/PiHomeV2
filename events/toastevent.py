import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent
from util.helpers import get_app


class ToastEvent(PihomeEvent):
    type = "toast"
    def __init__(self, message, level = "info", timeout = 5, **kwargs):
        super().__init__()
        self.message = message; 
        self.level = level
        self.timeout = timeout

    def execute(self):
        get_app().show_toast(self.message, self.level, self.timeout)


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "message": self.message,
            "level": self.level,
            "timeout": self.timeout
        })
