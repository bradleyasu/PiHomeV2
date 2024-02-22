
class PihomeEventType():
    COMMAND = "command"
    TIMER = "timer"
    APP = "app"
    IMAGE = "image"
    TOAST = "toast"
    TASK = "task"
    DISPLAY = "display"
    ALERT = "alert"
    TASK = "task"
    ACKTASK = "acktask" # Ack Task event will acknowledge active tasks


import json

from util.phlog import PIHOME_LOGGER


class PihomeEvent():
    def __init__(self):
        self.type = None

    def execute(self):
        print("Event Not Implemented")
        return {
            "code": 500,
            "body": {"status": "error", "message": "Event Not Implemented"}
        }

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
        from events.appevent import AppEvent
        from events.imageevent import ImageEvent
        from events.timerevent import TimerEvent
        from events.commandevent import CommandEvent
        from events.toastevent import ToastEvent
        from events.displayevent import DisplayEvent
        from events.alertevent import AlertEvent
        from events.taskevent import TaskEvent
        from events.acktaskevent import AckTaskEvent

        event_objects = {
            PihomeEventType.APP: AppEvent,
            PihomeEventType.IMAGE: ImageEvent,
            PihomeEventType.TIMER: TimerEvent,
            PihomeEventType.COMMAND: CommandEvent,
            PihomeEventType.TOAST: ToastEvent,
            PihomeEventType.DISPLAY: DisplayEvent,
            PihomeEventType.ALERT: AlertEvent,
            PihomeEventType.TASK: TaskEvent,
            PihomeEventType.ACKTASK: AckTaskEvent
        }
        try:
            event = event_objects[event_type]
            if event is None:
                PIHOME_LOGGER.error("Event type {} not found".format(event_type))
                return AlertEvent("Error", "Failed to process event \"{}\"".format(event_type), 20, 1)

            return event(**kwargs)
        except Exception as e:
            PIHOME_LOGGER.error("Error creating event: {}".format(event_type))
            PIHOME_LOGGER.error(e)
            from events.alertevent import AlertEvent
            return AlertEvent("Error", "{}".format(e), 20, 0)

    def create_event_from_dict(event_dict):
        return PihomeEventFactory.create_event(event_dict["type"], **event_dict)
        
    def create_event_from_json(json_string):
        return PihomeEventFactory.create_event_from_dict(json.loads(json_string))