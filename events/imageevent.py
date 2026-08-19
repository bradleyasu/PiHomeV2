import json

from kivy.clock import Clock
from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from util.const import _DISPLAY_IMAGE_SCREEN, _HOME_SCREEN
from util.helpers import prepare_display_image


class ImageEvent(PihomeEvent):
    type = "image"
    def __init__(self, image, timeout = 0, reload_interval = 0, **kwargs):
        super().__init__()
        self.image_url = image

        if  isinstance(timeout, str):
            timeout = int(timeout)
        self.timeout = timeout

        if isinstance(reload_interval, str):
            reload_interval = int(reload_interval)
        self.reload_interval = reload_interval

    def execute(self):
        screen = PIHOME_SCREEN_MANAGER.get_screen(_DISPLAY_IMAGE_SCREEN)
        screen.image = prepare_display_image(self.image_url)
        screen.reload_interval = self.reload_interval
        if self.timeout > 0:
            Clock.schedule_once(lambda _: screen.go_back(), self.timeout)
        PIHOME_SCREEN_MANAGER.goto(_DISPLAY_IMAGE_SCREEN)
        return {
            "code": 200,
            "body": {"status": "success", "message": "Image displayed"}
        }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "image": self.image_url,
            "timeout": self.timeout,
            "reload_interval": self.reload_interval
        })

    def to_definition(self):
        return {
            "type": self.type,
            "image": self.type_def("string"),
            "timeout": self.type_def("integer"),
            "reload_interval": self.type_def("integer")
        }