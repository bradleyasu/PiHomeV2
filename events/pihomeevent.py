
class PihomeEventType():
    COMMAND = "command"
    TIMER = "timer"
    APP = "app"
    IMAGE = "image"
    TOAST = "toast"
    TASK = "task"
    DISPLAY = "display"
    ALERT = "alert"


import json

from util.phlog import PIHOME_LOGGER


class PihomeEvent():
    def __init__(self):
        self.type = None

    def execute(self):
        print("Event Not Implemented")

    def to_json(self):
        return json.dumps({
            "type": self.type
        })

    def to_webhook(self):
        return json.dumps({
            "webhook": self.to_json() 
        })


class PihomeEventFactory():
    @staticmethod
    def create_event(event_type, **kwargs):
        try:
            if event_type == PihomeEventType.APP:
                from events.appevent import AppEvent
                return AppEvent(**kwargs)
            elif event_type == PihomeEventType.IMAGE:
                from events.imageevent import ImageEvent
                return ImageEvent(**kwargs)
            elif event_type == PihomeEventType.TIMER:
                from events.timerevent import TimerEvent
                return TimerEvent(**kwargs)
            elif event_type == PihomeEventType.COMMAND:
                from events.commandevent import CommandEvent
                return CommandEvent(**kwargs)
            elif event_type == PihomeEventType.TOAST:
                from events.toastevent import ToastEvent
                return ToastEvent(**kwargs)
            elif event_type == PihomeEventType.DISPLAY:
                from events.displayevent import DisplayEvent
                return DisplayEvent(**kwargs)
            elif event_type == PihomeEventType.ALERT:
                from events.alertevent import AlertEvent
                return AlertEvent(**kwargs)
            else:
                from events.alertevent import AlertEvent
                return AlertEvent("Warning", "Failed to process event {}".format(event_type), 20, 1)
        except Exception as e:
            PIHOME_LOGGER.error("Error creating event: {}".format(event_type))
            from events.alertevent import AlertEvent
            return AlertEvent("Error", "Failed to process event {}".format(event_type), 20, 0)

    def create_event_from_dict(event_dict):
        return PihomeEventFactory.create_event(event_dict["type"], **event_dict)
        
    def create_event_from_json(json_string):
        return PihomeEventFactory.create_event_from_dict(json.loads(json_string))