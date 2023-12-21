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
from PIL import ImageFilter as PILImageFilter
from kivy.network.urlrequest import UrlRequest
from util.const import TEMP_DIR
from util.helpers import get_app, get_config, get_poller, info, toast, url_hash
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
    current_color = "https://cdn.pihome.io/assets/background.jpg"
    default = "https://cdn.pihome.io/assets/background.jpg"
    source = ""
    allow_stretch = 1 

    cache = None
    repo = "CDN"
    poller_key = None
    url_cache = []
    cache_size = 30

    def __init__(self, **kwargs):
        super(Wallpaper, self).__init__(**kwargs)
        self._start()
    
    def restart(self):
        if self.poller_key != None:
            info("Wallpaper Service is restarting.  {} will be replaced with new thread".format(self.poller_key))
            get_poller().unregister_api(self.poller_key)
            self._start();

    def _start(self):
        self._cleanup()
        repo = get_config().get("wallpaper", "source", "PiHome CDN")
        self.allow_stretch = get_config().get_int("wallpaper", "allow_stretch", 1)
        self.repo = repo 
        info("Wallpaper service starting with source set to {} and allow stretch mode is set to {}".format(repo, self.allow_stretch))
        if repo == "Reddit":
            subs = get_config().get("wallpaper", "subreddits", "wallpaper")
            is_top = get_config().get_int("wallpaper", "top_of_all_time", 0)
            if subs == "":
                subs = "wallpaper"
            reddit_url = "https://www.reddit.com/r/{}.json?limit=100".format(subs)
            if is_top == 1:
                reddit_url = "https://www.reddit.com/r/{}/top/.json?limit=100&t=all".format(subs)
            self.poller_key = get_poller().register_api(reddit_url, 60 * 5, lambda json: self.parse_reddit(json));
        elif repo == "Wallhaven":
            search = get_config().get("wallpaper", "whsearch", "landscape")
            if search == "":
                search = "landscape"
            wh_url = "https://wallhaven.cc/api/v1/search?q={}&sorting=random".format(search)
            self.poller_key = get_poller().register_api(wh_url, 60 * 5, lambda json: self.parse_wallhaven(json))
        elif repo == "Custom":
            self.current = get_config().get("wallpaper", "custom_url", self.default)
            self.source = get_config().get("wallpaper", "custom_url", self.default)
            if self.current == "":
                self.current = self.default
        else:
            self.poller_key = get_poller().register_api("https://cdn.pihome.io/conf.json", 60 * 5, lambda json: self.parse_cdn(json));


    def parse_reddit(self, json):
        self.cache = json
        random_child = None
        while random_child == None or random_child["data"]["url"].endswith(".gif"):
            # select random child from json
            rand_idx = random.randint(0, len(json["data"]["children"])) - 1
            random_child = json["data"]["children"][rand_idx]

        self.current, self.current_color = self.resize_image(random_child["data"]["url"], 1024, 1024)
        self.source = random_child["data"]["url"]
        get_app()._reload_background()

    def parse_wallhaven(self, json): 
        self.cache = json
        skip_count = random.randint(0, 9)
        random_child = None
        while random_child == None or random_child["path"].endswith(".gif"):
            # select random child from json
            rand_idx = random.randint(0, len(json["data"])) - 1
            random_child = json["data"][rand_idx]
        
        self.current, self.current_color = self.resize_image(random_child["path"], 1024, 1024)
        self.source = random_child["path"]
        get_app()._reload_background()

    def parse_cdn(self, json):
        self.cache = json
        host = json["host"]
        background = json["background"]
        self.current = "{}{}".format(host, background)
        self.source = self.current
        get_app()._reload_background()


    def resize_image(self, url, width, height):
        hash = url_hash(url)
        resized = "_rsz_{}.png".format(hash)
        colored = "_color_{}.png".format(hash)

        if os.path.exists("{}/{}".format(TEMP_DIR, resized)) and os.path.exists("{}/{}".format(TEMP_DIR, colored)):
            info("Wallpaper Service: resizing wallpaper {} to fit in {}x{}".format(url, width, height))
            return "{}/{}".format(TEMP_DIR, resized), "{}/{}".format(TEMP_DIR, colored)

        self.url_cache.append(url)
        while len(self.url_cache) > self.cache_size:
            url = self.url_cache.pop(0)
            os.remove("{}/_rsz_{}.png".format(TEMP_DIR, url_hash(url)))
            os.remove("{}/_color_{}.png".format(TEMP_DIR, url_hash(url)))

        info("Wallpaper Service: resizing wallpaper {} to fit in {}x{}".format(url, width, height))
        r = requests.get(url)
        pilImage = PILImage.open(BytesIO(r.content), formats=("png", "jpeg"))

        # replace background with average color
        average_color = self.find_average_color(url)

        # resize image to fit screen and set background color to average color

        # pilImage = pilImage.resize((width, height), PILImage.ANTIALIAS)
        pilImage = ImageOps.contain(pilImage, (width, height))
        pilImage.save(fp="{}/{}".format(TEMP_DIR, resized), format="png")

        # create a new image with the average color as the background color and the pilImage centered in the foreground
        new_image = PILImage.new("RGB", (get_app().width, get_app().height), average_color)
        # stretch pilImage to fit screen and add to new image
        new_image.paste(pilImage, (0, 0))

        # blur image 
        new_image = new_image.filter(PILImageFilter.GaussianBlur(radius=5))
        new_image.save(fp="{}/{}".format(TEMP_DIR, colored), format="png")
        self.current_color = "{}/{}".format(TEMP_DIR, colored)

        info("Wallpaper Service: resizing wallpaper {} complete and located in {}".format(url, TEMP_DIR))
        return "{}/{}".format(TEMP_DIR, resized), "{}/{}".format(TEMP_DIR, colored)

    def find_average_color(self, url):
        info("Wallpaper Service: finding average color for {}".format(url))
        r = requests.get(url)
        pilImage = PILImage.open(BytesIO(r.content), formats=("png", "jpeg"))
        pilImage = pilImage.resize((1, 1), PILImage.ANTIALIAS)
        info("Wallpaper Service: finding average color for {} complete".format(url))
        info("Wallpaper Service: average color is {}".format(pilImage.getpixel((0, 0))))
        return pilImage.getpixel((0, 0))

    def _cleanup(self):
        # remove any tmp file with _rsz or _color in the name
        for file in os.listdir(TEMP_DIR):
            if file.startswith("_rsz") or file.startswith("_color"):
                os.remove("{}/{}".format(TEMP_DIR, file))

    def shuffle(self):
        toast("Shuffling wallpaper...", "info")
        url = self.get_random_from_cache()
        self.current, self.current_color = self.resize_image(url, 1024, 1024)
        self.source = url
        get_app()._reload_background()

        # if self.repo == "Reddit":
        #     self.parse_reddit(self.cache)
        # elif self.repo == "Wallhaven":
        #     self.parse_wallhaven(self.cache)
        # else:
        #     toast("Cannot shuffle wallpaper from configured source: {}".format(self.repo), "warn")

    def get_random_from_cache(self):
        random_idx = random.randint(0, len(self.url_cache) - 1)
        return self.url_cache[random_idx]