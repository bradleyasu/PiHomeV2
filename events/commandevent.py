
import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent
from util.const import MQTT_COMMANDS


class CommandEvent(PihomeEvent):
    def __init__(self, execute):
        super().__init__()
        self.type = "command"
        self.command = execute

    def execute(self):
        if self.command in MQTT_COMMANDS:
            MQTT_COMMANDS[self.command]()


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "command": self.command
        })
