

import json
from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from util.const import _DISPLAY_SCREEN


class DisplayEvent(PihomeEvent):
    type = "display"
    def __init__(self, title, message, image, background = None, timeout = None, **kwargs):
        super().__init__()
        self.title = title
        self.message = message
        self.image = image
        self.background = background
        self.timeout = timeout

    def execute(self):
        screen = PIHOME_SCREEN_MANAGER.get_screen(_DISPLAY_SCREEN)
        screen.title = self.title
        screen.message = self.message
        screen.image = self.image
        if self.background is not None:
            screen.background = self.background
        if self.timeout is not None:
            screen.set_timeout(self.timeout)
        PIHOME_SCREEN_MANAGER.goto(_DISPLAY_SCREEN)

        return {
            "code": 200,
            "body": {"status": "success", "message": "Display updated"}
        }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "image": self.image,
            "background": self.background,
            "timeout": self.timeout
        })

    def to_definition(self):
        return {
            "type": self.type,
            "title": self.type_def("string"),
            "message": self.type_def("string"),
            "image": self.type_def("string"),
            "background": self.type_def("string", False),
            "timeout": self.type_def("integer", False)
        }