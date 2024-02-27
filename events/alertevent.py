
import json
from components.Msgbox.msgbox import MSGBOX_BUTTONS, MSGBOX_FACTORY, MSGBOX_TYPES
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER


class AlertEvent(PihomeEvent):
    type = "alert"
    def __init__(self, title, message, timeout, level = MSGBOX_TYPES["INFO"], buttons = MSGBOX_BUTTONS["OK"], on_yes = None, on_no = None, **kwargs):
        super().__init__()
        self.timeout = timeout
        self.title = title
        self.message = message
        self.level = level
        self.buttons = buttons
        self.on_yes = on_yes
        self.on_no = on_no


    def execute(self):
        MSGBOX_FACTORY.show(self.title, self.message, self.timeout, self.type, self.buttons, self.on_yes, self.on_no)
        return {
            "code": 200,
            "body": {"status": "success", "message": "Alert displayed"}
        }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "timeout": self.timeout,
            "type": self.type,
            "buttons": self.buttons,
            "on_yes": self.on_yes,
            "on_no": self.on_no
        })

    def to_definition(self):
        return {
            "type": self.type,
            "title": self.type_def("string"),
            "message": self.type_def("string"),
            "timeout": self.type_def("integer"),
            "level": self.type_def("string"),
            "buttons": self.type_def("string"),
            "on_yes": self.type_def("string", False),
            "on_no": self.type_def("string", False)
        }