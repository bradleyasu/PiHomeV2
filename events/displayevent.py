

import json
from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from util.const import _DISPLAY_SCREEN


class DisplayEvent(PihomeEvent):
    def __init__(self, title, message, image, background = None, timeout = None, **kwargs):
        super().__init__()
        self.type = "display"
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
            screen.set_timeout(self.timeout, _DISPLAY_SCREEN)
        PIHOME_SCREEN_MANAGER.goto(_DISPLAY_SCREEN)


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "image": self.image,
            "background": self.background,
            "timeout": self.timeout
        })
