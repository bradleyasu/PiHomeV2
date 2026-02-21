import time
import threading

from events.pihomeevent import PihomeEventFactory
from util.phlog import PIHOME_LOGGER

"""
Simple Timer class with start, stop, and reset methods.
"""
class Timer:
    # on_complete should be a PihomeEvent
    def __init__(self, duration = 0, label = None, on_complete = None):
        self.start_time = 0
        self.end_time = self.start_time + duration
        self.elapsed_time = 0
        self.is_running = False
        self.listeners = []
        if label is None:
            label = "{} second timer".format(duration)
        self.label = label
        self.duration = duration
        self.on_complete = on_complete
        self.start_time = time.time()
        if self.on_complete is not None:
            self.add_listener(lambda _: self.process_on_complete())
        
    def to_dict(self):
        return {
            "label": self.label,
            "duration": self.duration,
            "start_time": self.start_time,
            "on_complete": self.on_complete
        }

    def process_on_complete(self):
        event = self.generate_event(self.on_complete)
        if event is not None:
            event.execute()
    
    def generate_event(self, event_json):
        event = None
        if event_json is None:
            return event
        try:
            event = PihomeEventFactory.create_event_from_dict(event_json)
        except Exception as e:
            PIHOME_LOGGER.error(f"Error generating event from json: {e}")
        return event

    def update(self):
        while self.is_running:
            if self.is_running:
                self.elapsed_time = time.time() - self.start_time
                if self.elapsed_time >= self.end_time:
                    self.stop(notify=True)
            time.sleep(0.1)


    def add_listener(self, listener):
        self.listeners.append(listener)

    def remove_listener(self, listener):
        self.listeners.remove(listener)
    
    def notify_listeners(self):
        for listener in self.listeners:
            listener(self.get_elapsed_time())

    def cancel(self):
        self.stop(notify=True)
        self.is_running = False
    
    def start(self):
        if self.is_running:
            return
        self.start_time = time.time()
        self.is_running = True
        threading.Thread(target=self.update, daemon=True).start()

    def stop(self, notify=False):
        """
        Stop the timer and notify listeners if requested.
        notify: bool - If True, notify listeners
        """
        self.end_time = time.time()
        self.elapsed_time = self.end_time - self.start_time
        self.is_running = False
        if notify:
            self.notify_listeners()

    def reset(self):
        self.start_time = 0
        self.end_time = 0
        self.elapsed_time = 0
        self.is_running = False

    def get_elapsed_time(self):
        rounded = round(self.elapsed_time, 1)
        return rounded
            

