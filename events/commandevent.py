
import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent
from util.const import MQTT_COMMANDS


class CommandEvent(PihomeEvent):
    type = "command"
    def __init__(self, execute, **kwargs):
        super().__init__()
        self.command = execute

    def execute(self):
        if self.command in MQTT_COMMANDS:
            MQTT_COMMANDS[self.command]()
            return {
                "code": 200,
                "body": {"status": "success", "message": "Command executed"}
            }
        else:
            return {
                "code": 400,
                "body": {"status": "error", "message": "Command not found"}
            }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "command": self.command
        })
