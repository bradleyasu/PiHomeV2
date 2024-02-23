
import importlib
import inspect
import json
import os

from util.phlog import PIHOME_LOGGER


class PihomeEvent():
    type = "event"
    def __init__(self):
        pass

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
        event_objects = PihomeEventFactory._load_event_objects()
        
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

    def _load_event_objects():
        """
        This function will read all the events in this directory and load them into the event_objects dictionary.
        """
        events_dir = "./events/"
        event_objects = {}
        for root, dirs, files in os.walk(events_dir):
            for file in files:
                if file.endswith(".py") and file != "__init__.py" and file != "pihomeevent.py":
                    directory = os.path.dirname(os.path.abspath(__file__))
                    module_name = os.path.splitext(file)[0]
                    module_path = os.path.join(directory, file)

                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for _, obj in inspect.getmembers(module):
                        if inspect.isclass(obj):
                            class_name = getattr(obj, "type", None)
                            if class_name is not None and class_name != "event" and class_name != "PihomeEvent":
                                event_objects[class_name] = obj
        return event_objects

    def create_event_from_dict(event_dict):
        return PihomeEventFactory.create_event(event_dict["type"], **event_dict)
        
    def create_event_from_json(json_string):
        return PihomeEventFactory.create_event_from_dict(json.loads(json_string))