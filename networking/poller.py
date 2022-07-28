import os
import time
import requests
from threading import Thread

from util.helpers import get_app

class Poller:

    def __init__(self):
        pass

    def register_api(self, url, key, interval, on_resp):
        ApiCall(url, key, interval, on_resp).start();
        pass


"""
    Thread class used for polling api calls at specified intrvals
"""
class ApiCall(Thread):
    def __init__(self, url, key, interval, on_resp):
        Thread.__init__(self)
        self.url = url
        self.key = key
        self.interval = interval;
        self.on_resp = on_resp

    def run(self):
        while True:
            d = requests.get(self.url)
            if(d.status_code == 200):
                json = d.json()
                self.on_resp(json)
            time.sleep(self.interval)
