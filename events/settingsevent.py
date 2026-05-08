import json

from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER


class SettingsEvent(PihomeEvent):
    type = "settings"

    def __init__(self, section, key, value, **kwargs):
        super().__init__()
        self.section = section
        self.key = key
        self.value = value

    def execute(self):
        if not self.section or not self.key:
            return {
                "code": 400,
                "body": {"status": "error", "message": "section and key are required"},
            }
        if self.value is None:
            return {
                "code": 400,
                "body": {"status": "error", "message": "value is required"},
            }

        if isinstance(self.value, bool):
            stored = "1" if self.value else "0"
        else:
            stored = str(self.value)

        PIHOME_LOGGER.info(
            "SettingsEvent: setting [{}].{} = {}".format(self.section, self.key, stored)
        )
        CONFIG.set(self.section, self.key, stored)
        PIHOME_SCREEN_MANAGER.reload_all()

        return {
            "code": 200,
            "body": {
                "status": "success",
                "message": "[{}].{} set to {}".format(self.section, self.key, stored),
            },
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "section": self.section,
            "key": self.key,
            "value": self.value,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "section": self.type_def("string", True, "INI section name (e.g. 'bambulab', 'theme')"),
            "key": self.type_def("string", True, "INI key within the section (e.g. 'enabled', 'dark_mode')"),
            "value": self.type_def("string", True, "New value to write. Booleans become '1'/'0'; numbers are stringified. base.ini stores all values as strings."),
        }
