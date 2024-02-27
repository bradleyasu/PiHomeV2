
import json

from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER


class AppEvent(PihomeEvent):
    type = "app"
    def __init__(self, app, **kwargs):
        super().__init__()
        self.app = app

    def execute(self):
        PIHOME_SCREEN_MANAGER.goto(self.app)
        return {
            "code": 200,
            "body": {"status": "success", "message": "App launched"}
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "app": self.app
        }
    )

    def to_definition(self):
        return {
            "type": self.type,
            "app": self.type_def("string")
        }