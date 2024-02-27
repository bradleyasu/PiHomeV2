import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent
from services.audio.sfx import SFX
from util.phlog import PIHOME_LOGGER


class SfxEvent(PihomeEvent):
    type = "sfx"
    def __init__(self, name, state = "play", loop = False, **kwargs):
        super().__init__()
        self.name = name
        self.state = state
        self.loop = loop

    def execute(self):
        PIHOME_LOGGER.info("Executing SFX Event: {} with state: {} and loop: {}".format(self.name, self.state, self.loop))
        if SFX.has(self.name):
            if self.state == "play":
                if self.loop:
                    SFX.loop(self.name)
                else:
                    SFX.play(self.name)
            elif self.state == "stop":
                SFX.stop(self.name)
            return {
                "code": 200,
                "body": {"status": "success", "message": "SFX action executed successfully"}
            }
        else:
            return {
                "code": 400,
                "body": {"status": "error", "message": "Invalid SFX name", "valid_sfx": list(SFX.SOUND_EFFECTS.keys())}
            }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "name": self.name,
            "state": self.state,
            "loop": self.loop
        })

    def to_definition(self):
        return {
            "type": self.type,
            "name": self.type_def("string"),
            "state": self.type_def("string"),
            "loop": self.type_def("boolean", False)
        }