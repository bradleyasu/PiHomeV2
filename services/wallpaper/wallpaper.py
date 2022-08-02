from datetime import datetime
import random
import os
import time
import requests
from threading import Thread
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from util.helpers import get_app, get_config, get_poller, toast

class Wallpaper:
    """
    Service that will continuously ping external services for fresh wallpaper depending
    on user configuations.  The 'current' property will have the currently selected
    wallpaper which can be set from the following services:
        1: PiHole CDN
        2: Reddit/Subreddit configurations
        3: Custom URL
        4: {Add additional services}
    """

    current = "https://cdn.pihome.io/assets/background.jpg"
    default = "https://cdn.pihome.io/assets/background.jpg"
    allow_stretch = 1 

    def __init__(self, **kwargs):
        super(Wallpaper, self).__init__(**kwargs)
        source = get_config().get("wallpaper", "source", "PiHome CDN")
        self.allow_stretch = get_config().get_int("wallpaper", "allow_stretch", 1)
        if source == "Reddit":
            subs = get_config().get("wallpaper", "subreddits", "wallpaper")
            if subs == "":
                subs = "wallpaper"
            reddit_url = "https://www.reddit.com/r/{}.json?limit=100".format(subs)
            get_poller().register_api(reddit_url, 60 * 5, lambda json: self.parse_reddit(json));
        elif source == "Custom":
            self.current = get_config().get("wallpaper", "custom_url", self.default)
            if self.current == "":
                self.current = self.default
        else:
            get_poller().register_api("https://cdn.pihome.io/conf.json", 60 * 5, lambda json: self.parse_cdn(json));

    def parse_reddit(self, json):
        skip_count = random.randint(0, 9)
        print("skip count: {}".format(skip_count))
        for value in json["data"]["children"]:
            if skip_count <= 0 and "url" in value["data"] and (value["data"]["url"].endswith(".png") or value["data"]["url"].endswith(".jpg")):
                self.current = value["data"]["url"]
                break
            skip_count = skip_count - 1

    def parse_cdn(self, json):
        host = json["host"]
        background = json["background"]
        self.current = "{}{}".format(host, background)
