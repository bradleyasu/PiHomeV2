import json

from events.pihomeevent import PihomeEvent
from system.brightness import set_brightness
from util.phlog import PIHOME_LOGGER


class BrightnessEvent(PihomeEvent):
    type = "brightness"
    def __init__(self, level, **kwargs):
        super().__init__()
        self.level = int(level) if level is not None else 100

    def execute(self):
        clamped = max(0, min(100, self.level))
        PIHOME_LOGGER.info("BrightnessEvent: setting brightness to {}%".format(clamped))
        set_brightness(clamped)
        return {
            "code": 200,
            "body": {"status": "success", "message": "Brightness set to {}%".format(clamped)}
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "level": self.level
        })

    def to_definition(self):
        return {
            "type": self.type,
            "level": self.type_def("number", required=True, description="Brightness level (0-100%)"),
        }
