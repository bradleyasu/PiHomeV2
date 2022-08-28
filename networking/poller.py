from operator import mod
import os
import time
import requests
from threading import Thread
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from util.helpers import error, get_app, info, random_hash, toast

class Poller:

    registered_calls = {}
    MAX_TICK = 86400
    tick = 0

    def __init__(self, **kwargs):
        super(Poller, self).__init__(**kwargs)
        Clock.schedule_interval(lambda _: self._tick(), 1)

    def _tick(self):
        self.tick = self.tick + 1
        if self.tick >= self.MAX_TICK:
            self.tick = 0
        for k,v in self.registered_calls.items():
            if self.tick % int(v["interval"]) == 0:
                info("[ {} ] Poller triggering {}".format(k, v["url"]))
                self.api_call(v["url"], v["on_resp"])

    def register_api(self, url, interval, on_resp):
        phash = random_hash()
        Clock.schedule_once(lambda _: self.api_call(url, on_resp), 2)
        self.registered_calls[phash] = {"url": url, "interval": interval, "on_resp": on_resp}
        info("Poller registered {} with {} at interval {} seconds".format(phash, url, interval))
        return phash


    # def register_api(self, url, interval, on_resp):
        # Clock.schedule_once(lambda _: self.api_call(url, on_resp), 2)
        # Clock.schedule_interval(lambda _: self.api_call(url, on_resp), interval)

    def api_call(self, url, on_resp):
        url = url.replace(" ", "%20")
        info("[ POLL ] Initializing API Call: {}".format(url))
        req = UrlRequest(
            url=url, 
            on_success = lambda request, 
            result: on_resp(result),
            on_error=lambda r, d: error("An Error Occurred while polling api. {}".format(d)),
            on_failure=lambda r, d: error("A failure occurred while polling api. {}".format(d))
        )