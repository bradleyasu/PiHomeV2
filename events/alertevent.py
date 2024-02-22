
import json
from components.Msgbox.msgbox import MSGBOX_BUTTONS, MSGBOX_FACTORY, MSGBOX_TYPES
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER


class AlertEvent(PihomeEvent):
    def __init__(self, title, message, timeout, level = MSGBOX_TYPES["INFO"], buttons = MSGBOX_BUTTONS["OK"], on_yes = None, on_no = None, **kwargs):
        super().__init__()
        self.type = "toast"
        self.timeout = timeout
        self.title = title
        self.message = message
        self.type = level
        self.buttons = buttons
        self.on_yes = on_yes
        self.on_no = on_no


    def execute(self):
        current_screen = PIHOME_SCREEN_MANAGER.current_screen
        MSGBOX_FACTORY.show(current_screen, self.title, self.message, self.timeout, self.type, self.buttons, self.on_yes, self.on_no)


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
