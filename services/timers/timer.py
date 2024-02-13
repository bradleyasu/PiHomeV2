import asyncio
import time
import threading

from util.helpers import info
"""
Simple Timer class with start, stop, and reset methods.
"""
class Timer:
    def __init__(self, duration = 0, label = None):
        self.start_time = 0
        self.end_time = self.start_time + duration
        self.elapsed_time = 0
        self.is_running = False
        self.listeners = []
        if label is None:
            label = "{} second timer".format(duration)
        self.label = label
        self.duration = duration

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
    
    def start(self):
        if self.is_running:
            return
        self.start_time = time.time()
        self.is_running = True
        threading.Thread(target=self.update).start()

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
            
