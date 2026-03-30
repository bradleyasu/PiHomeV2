import json

from events.pihomeevent import PihomeEvent
from util.helpers import get_app


class ToastEvent(PihomeEvent):
    type = "toast"
    def __init__(self, message, level="info", timeout=5, **kwargs):
        super().__init__()
        self.message = message
        self.level = level
        self.timeout = timeout

    def execute(self):
        success = get_app().show_toast(self.message, self.level, self.timeout)
        if not success:
            return {
                "code": 400,
                "body": {"status": "error", "message": "Failed to display toast"}
            }
        return {
            "code": 200,
            "body": {"status": "success", "message": "Toast displayed"}
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "message": self.message,
            "level": self.level,
            "timeout": self.timeout
        })

    def to_definition(self):
        return {
            "type": self.type,
            "message": self.type_def("string", required=True, description="The toast message text"),
            "level": self.type_def("option", required=False, description="Toast level", options=["info", "warning", "error", "success"]),
            "timeout": self.type_def("number", required=False, description="Duration in seconds to display the toast"),
        }
