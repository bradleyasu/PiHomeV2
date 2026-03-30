import json

from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER


class ThemeEvent(PihomeEvent):
    type = "theme"
    def __init__(self, mode, **kwargs):
        super().__init__()
        self.mode = mode

    def execute(self):
        if self.mode == "toggle":
            current = CONFIG.get_int("theme", "dark_mode", 0)
            new_val = "0" if current == 1 else "1"
        elif self.mode == "dark":
            new_val = "1"
        elif self.mode == "light":
            new_val = "0"
        else:
            return {
                "code": 400,
                "body": {"status": "error", "message": "Invalid mode: {}".format(self.mode)}
            }

        PIHOME_LOGGER.info("ThemeEvent: setting dark_mode to {}".format(new_val))
        CONFIG.set("theme", "dark_mode", new_val)
        PIHOME_SCREEN_MANAGER.reload_all()
        return {
            "code": 200,
            "body": {"status": "success", "message": "Theme set to {}".format("dark" if new_val == "1" else "light")}
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "mode": self.mode
        })

    def to_definition(self):
        return {
            "type": self.type,
            "mode": self.type_def("option", required=True, description="Theme mode to apply", options=["dark", "light", "toggle"]),
        }
