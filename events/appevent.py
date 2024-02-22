
import json

from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER


class AppEvent(PihomeEvent):
    def __init__(self, app, **kwargs):
        super().__init__()
        self.type = "app"
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