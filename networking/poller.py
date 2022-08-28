import os
import time
import requests
from threading import Thread
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from util.helpers import error, get_app, info, toast

class Poller:

    def __init__(self, **kwargs):
        super(Poller, self).__init__(**kwargs)

    def register_api(self, url, interval, on_resp):
        Clock.schedule_once(lambda _: self.api_call(url, on_resp), 2)
        Clock.schedule_interval(lambda _: self.api_call(url, on_resp), interval)

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