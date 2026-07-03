
import importlib.util
import inspect
import json
import os
import threading

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

    def execute_safe(self, timeout=10):
        """Execute this event on the Kivy main thread and return its response.

        Most events mutate Kivy widgets (screens, toasts, notifications),
        which is only safe on the main thread. Entry points that run on other
        threads (HTTP server, WebSocket, MQTT, timers, background services)
        must call this instead of execute(). Runs inline when already on the
        main thread, so it is always safe to use.
        """
        from util.helpers import run_on_main_thread
        return run_on_main_thread(self.execute, timeout=timeout)

    def to_json(self):
        return json.dumps({
            "type": self.type
    })

    def to_definition(self):
        None
    
    def type_def(self, type, required = True, description = None, options = []):
        return {
            "type": type,
            "required": required,
            "description": description,
            "options": options,
        }

    def to_webhook(self):
        return json.dumps({
            "webhook": self.to_json() 
        })

class PihomeEventFactory():
    # Event registry cache: scanning ./events/ and every screens/*/events/
    # directory re-executes ~40 modules from disk, far too expensive to do on
    # every event (the web client alone requests a status event every second).
    # Events only change with a code update, which restarts PiHome, so the
    # registry is built once and cached for the process lifetime.
    _registry = None
    _registry_lock = threading.Lock()

    @staticmethod
    def create_event(event_type, **kwargs):
        from events.alertevent import AlertEvent
        event_objects = PihomeEventFactory._load_event_objects()

        event = event_objects.get(event_type)
        if event is None:
            PIHOME_LOGGER.error("Event type {} not found".format(event_type))
            return AlertEvent("Error", "Failed to process event \"{}\"".format(event_type), 20, 1)
        try:
            return event(**kwargs)
        except Exception as e:
            PIHOME_LOGGER.error("Error creating event: {}".format(event_type))
            PIHOME_LOGGER.error(e)
            return AlertEvent("Error", "{}".format(e), 20, 0)

    @staticmethod
    def _load_event_objects():
        """Return the event-type -> class registry, building it on first use."""
        registry = PihomeEventFactory._registry
        if registry is not None:
            return registry
        with PihomeEventFactory._registry_lock:
            if PihomeEventFactory._registry is None:
                PihomeEventFactory._registry = PihomeEventFactory._build_event_registry()
            return PihomeEventFactory._registry

    @staticmethod
    def reload_events():
        """Drop the cached registry and rescan event modules from disk.

        Only needed if event files change while PiHome is running (e.g. a
        screen directory is dropped in without a restart).
        """
        with PihomeEventFactory._registry_lock:
            PihomeEventFactory._registry = None
        return PihomeEventFactory._load_event_objects()

    @staticmethod
    def _build_event_registry():
        """
        This function will read all the events in this directory and load them into the event_objects dictionary.
        It also scans each screen's optional events/ subdirectory for screen-specific events.
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

        # Scan screen-specific events/ subdirectories
        screens_dir = "./screens/"
        if os.path.isdir(screens_dir):
            for screen in os.listdir(screens_dir):
                screen_events_dir = os.path.join(screens_dir, screen, "events")
                if not os.path.isdir(screen_events_dir):
                    continue
                for file in os.listdir(screen_events_dir):
                    if not file.endswith(".py") or file == "__init__.py":
                        continue
                    module_name = os.path.splitext(file)[0]
                    module_path = os.path.join(screen_events_dir, file)
                    try:
                        spec = importlib.util.spec_from_file_location(module_name, os.path.abspath(module_path))
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        for _, obj in inspect.getmembers(module):
                            if inspect.isclass(obj):
                                class_name = getattr(obj, "type", None)
                                if class_name is not None and class_name != "event" and class_name != "PihomeEvent":
                                    if class_name in event_objects:
                                        PIHOME_LOGGER.warning(
                                            f"Screen event type '{class_name}' from {module_path} "
                                            f"conflicts with existing event — skipping"
                                        )
                                    else:
                                        event_objects[class_name] = obj
                    except Exception as e:
                        PIHOME_LOGGER.error(f"Error loading screen event from {module_path}: {e}")

        return event_objects

    def create_event_from_dict(event_dict):
        return PihomeEventFactory.create_event(event_dict["type"], **event_dict)
        
    def create_event_from_json(json_string):
        return PihomeEventFactory.create_event_from_dict(json.loads(json_string))


    def get_event_definitions():
        event_objects = PihomeEventFactory._load_event_objects()
        events = []
        for key in event_objects:
            event = PihomeEventFactory._dumb_init(event_objects[key]) 
            event_def = event.to_definition()
            if event_def is not None:
                events.append(event_def)
        return events
    
    def _dumb_init(cls):
        argspec = inspect.signature(cls.__init__)
        dummy_args = {param.name: None for param in argspec.parameters.values() if param.default == param.empty}
        dummy_args.pop("self", None)
        return cls(**dummy_args)
    