import base64
from datetime import datetime
from io import BytesIO
import random
import os
import time
import requests
from threading import Thread
from kivy.clock import Clock
from PIL import Image as PILImage, ImageOps
from kivy.network.urlrequest import UrlRequest
from util.const import TEMP_DIR
from util.helpers import get_app, get_config, get_poller, info, toast
from kivy.uix.image import Image, CoreImage

class Wallpaper:
    """
    Service that will continuously ping external services for fresh wallpaper depending
    on user configuations.  The 'current' property will have the currently selected
    wallpaper which can be set from the following services:
        1: PiHome CDN
        2: Reddit/Subreddit configurations
        3: Custom URL
        4: {Add additional services}
    """

    current = "https://cdn.pihome.io/assets/background.jpg"
    default = "https://cdn.pihome.io/assets/background.jpg"
    allow_stretch = 1 

    cache = None
    source = "CDN"

    def __init__(self, **kwargs):
        super(Wallpaper, self).__init__(**kwargs)
        source = get_config().get("wallpaper", "source", "PiHome CDN")
        self.allow_stretch = get_config().get_int("wallpaper", "allow_stretch", 1)
        self.source =source
        if source == "Reddit":
            subs = get_config().get("wallpaper", "subreddits", "wallpaper")
            if subs == "":
                subs = "wallpaper"
            reddit_url = "https://www.reddit.com/r/{}.json?limit=100".format(subs)
            get_poller().register_api(reddit_url, 60 * 5, lambda json: self.parse_reddit(json));
        elif source == "Wallhaven":
            search = get_config().get("wallpaper", "whsearch", "landscape")
            if search == "":
                search = "landscape"
            wh_url = "https://wallhaven.cc/api/v1/search?q={}".format(search)
            get_poller().register_api(wh_url, 60 * 5, lambda json: self.parse_wallhaven(json))
        elif source == "Custom":
            self.current = get_config().get("wallpaper", "custom_url", self.default)
            if self.current == "":
                self.current = self.default
        else:
            get_poller().register_api("https://cdn.pihome.io/conf.json", 60 * 5, lambda json: self.parse_cdn(json));

    def parse_reddit(self, json):
        self.cache = json
        skip_count = random.randint(0, 9)
        for value in json["data"]["children"]:
            if skip_count <= 0 and "url" in value["data"] and (value["data"]["url"].endswith(".png") or value["data"]["url"].endswith(".jpg")):
                self.current = self.resize_image(value["data"]["url"], 1024, 1024)
                get_app()._reload_background()
                # self.current = value["data"]["url"]
                break
            if "url" in value["data"] and (value["data"]["url"].endswith(".png") or value["data"]["url"].endswith(".jpg")):
                skip_count = skip_count - 1

    def parse_wallhaven(self, json): 
        self.cache = json
        skip_count = random.randint(0, 9)
        for value in json["data"]:
            if skip_count <= 0 and "path" in value and (value["path"].endswith(".png") or value["path"].endswith(".jpg")):
                self.current = self.resize_image(value["path"], 1024, 1024)
                get_app()._reload_background()
                # self.current = value["data"]["url"]
                break
            if "path" in value and (value["path"].endswith(".png") or value["path"].endswith(".jpg")):
                skip_count = skip_count - 1

    def parse_cdn(self, json):
        self.cache = json
        host = json["host"]
        background = json["background"]
        self.current = "{}{}".format(host, background)
        get_app()._reload_background()


    def resize_image(self, url, width, height):
        info("Wallpaper Service: resizing wallpaper {} to fit in {}x{}".format(url, width, height))
        r = requests.get(url)
        pilImage = PILImage.open(BytesIO(r.content), formats=("png", "jpeg"))
        # pilImage = pilImage.resize((width, height), PILImage.ANTIALIAS)
        pilImage = ImageOps.contain(pilImage, (width, height))
        pilImage.save(fp="{}/_rsz_.png".format(TEMP_DIR), format="png")
        info("Wallpaper Service: resizing wallpaper {} complete and located in {}".format(url, TEMP_DIR))
        return "{}/_rsz_.png".format(TEMP_DIR)

    def shuffle(self):
        if self.source == "Reddit":
            self.parse_reddit(self.cache)
        elif self.source == "Wallhaven":
            self.parse_wallhaven(self.cache)
        else:
            toast("Cannot shuffle wallpaper from configured source", "warn")