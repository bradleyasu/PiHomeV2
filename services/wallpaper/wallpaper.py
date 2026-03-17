from io import BytesIO
import random
import os
import PIL
import requests
from kivy.clock import Clock
from PIL import Image as PILImage, ImageOps
from PIL import ImageFilter as PILImageFilter
from networking.poller import POLLER
from services.audio.sfx import SFX
from util.configuration import CONFIG
from util.const import TEMP_DIR
from util.helpers import get_app, toast, url_hash
import asyncio
import json
import threading

from util.phlog import PIHOME_LOGGER


BAN_LIST_JSON = "./ban_list.pihome"
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
    shuffle_index = 0
    cache_size = 100
    ban_list = [] # URLs that are not allowed to be used as wallpapers
    paused = False
    # Snapshotted at _start() time; compared in restart() to detect real source changes
    _active_source = None
    _active_subs   = None
    _active_top    = None
    _active_wh     = None
    _active_custom = None

    def __init__(self, **kwargs):
        super(Wallpaper, self).__init__(**kwargs)
        Clock.schedule_once(lambda _: self._start(), 30)

        # Deserialize ban list
        self.deserialize_ban_list()


    def serialize_ban_list(self):
        """
        This function will serialize the ban list to a json file on disk
        """
        with open(BAN_LIST_JSON, "w") as f:
            f.write(json.dumps(self.ban_list))
        
    def deserialize_ban_list(self):
        """
        This function will deserialize the ban list from a json file on disk
        """
        if os.path.exists(BAN_LIST_JSON):
            with open(BAN_LIST_JSON, "r") as f:
                self.ban_list = json.loads(f.read())
        
        # Log ban list
        for url in self.ban_list:
            PIHOME_LOGGER.info("Wallpaper Service: banned url {}".format(url))

    
    def restart(self):
        """Restart the wallpaper service.  The cache is only cleared when the
        source or its relevant sub-settings actually changed — so saving unrelated
        settings (theme, pi-hole, etc.) won't flush already-downloaded images.

        NOTE: CONFIG.reload() has already run before this is called, so the
        CONFIG object already holds new values.  We compare against the
        _active_* attributes that were snapshotted when _start() last ran.
        """
        new_source  = CONFIG.get("wallpaper", "source", "PiHome CDN")
        new_stretch = CONFIG.get_int("wallpaper", "allow_stretch", 1)
        new_subs    = CONFIG.get("wallpaper", "subreddits", "wallpaper")
        new_top     = CONFIG.get_int("wallpaper", "top_of_all_time", 0)
        new_wh      = CONFIG.get("wallpaper", "whsearch", "landscape")
        new_custom  = CONFIG.get("wallpaper", "custom_url", self.default)

        # Compare against values that were active when _start() last ran
        source_changed = (
            new_source != self._active_source
            or new_subs    != self._active_subs
            or new_top     != self._active_top
            or new_wh      != self._active_wh
            or new_custom  != self._active_custom
        )

        # allow_stretch can be applied immediately without invalidating the cache
        self.allow_stretch = new_stretch

        if not source_changed:
            PIHOME_LOGGER.info("Wallpaper Service: source unchanged, skipping restart.")
            return

        if self.poller_key is not None:
            PIHOME_LOGGER.info("Wallpaper Service is restarting.  {} will be replaced with new thread".format(self.poller_key))
            POLLER.unregister_api(self.poller_key)
        self._start()

    def _start(self):
        self._cleanup()
        repo = CONFIG.get("wallpaper", "source", "PiHome CDN")
        self.allow_stretch = CONFIG.get_int("wallpaper", "allow_stretch", 1)
        self.repo = repo
        # Snapshot the active sub-settings so restart() can detect real changes
        self._active_source = repo
        self._active_subs   = CONFIG.get("wallpaper", "subreddits", "wallpaper")
        self._active_top    = CONFIG.get_int("wallpaper", "top_of_all_time", 0)
        self._active_wh     = CONFIG.get("wallpaper", "whsearch", "landscape")
        self._active_custom = CONFIG.get("wallpaper", "custom_url", self.default) 
        PIHOME_LOGGER.info("Wallpaper service starting with source set to {} and allow stretch mode is set to {}".format(repo, self.allow_stretch))
        if repo == "Reddit":
            subs = CONFIG.get("wallpaper", "subreddits", "wallpaper")
            is_top = CONFIG.get_int("wallpaper", "top_of_all_time", 0)
            if subs == "":
                subs = "wallpaper"
            reddit_url = "https://www.reddit.com/r/{}.json?limit=100".format(subs)
            if is_top == 1:
                reddit_url = "https://www.reddit.com/r/{}/top/.json?limit=100&t=all".format(subs)
            self.poller_key = POLLER.register_api(reddit_url, 60 * 5, lambda json: self.parse_reddit(json));
        elif repo == "Wallhaven":
            search = CONFIG.get("wallpaper", "whsearch", "landscape")
            if search == "":
                search = "landscape"
            wh_url = "https://wallhaven.cc/api/v1/search?q={}&sorting=random".format(search)
            self.poller_key = POLLER.register_api(wh_url, 60 * 5, lambda json: self.parse_wallhaven(json))
        elif repo == "Custom":
            custom_url = CONFIG.get("wallpaper", "custom_url", self.default)
            self.poller_key = POLLER.register_api(custom_url, 60 * 5, lambda json: self.parse_custom(json));
        else:
            self.poller_key = POLLER.register_api("https://cdn.pihome.io/conf.json", 60 * 5, lambda json: self.parse_cdn(json));


    def parse_custom(self, json):
        if self.paused:
            return
        self.cache = json
        source = json.get("img", self.default)
        self.current, self.current_color = self.resize_image(source, 1024, 1024)
        self.source = source
        get_app()._reload_background()

    def parse_reddit(self, json):
        if self.paused:
            return
        self.cache = json
        random_child = None
        while random_child == None or random_child["data"]["url"].endswith(".gif") or random_child["data"]["url"] in self.ban_list:
            # select random child from json
            rand_idx = random.randint(0, len(json["data"]["children"])) - 1
            random_child = json["data"]["children"][rand_idx]


        self.current, self.current_color = self.resize_image(random_child["data"]["url"], 1024, 1024)
        self.source = random_child["data"]["url"]
        get_app()._reload_background()

    async def create_cache(self, urls):
        for url in urls:
            print("creating cache for", url)
            if url.endswith(".jpg") or url.endswith(".png"):
                self.resize_image(url, 1024, 1024)
        await asyncio.sleep(0)

    def parse_wallhaven(self, json): 
        if self.paused:
            return
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
            PIHOME_LOGGER.info("Wallpaper Service: cache hit for wallpaper {}".format(url))
            # Still track this URL so next()/previous() can navigate to it sequentially
            if url not in self.url_cache:
                self.url_cache.append(url)
            return "{}/{}".format(TEMP_DIR, resized), "{}/{}".format(TEMP_DIR, colored)

        self.url_cache.append(url)
        while len(self.url_cache) > self.cache_size:
            evicted = self.url_cache.pop(0)
            try:
                os.remove("{}/_rsz_{}.png".format(TEMP_DIR, url_hash(evicted)))
                os.remove("{}/_color_{}.png".format(TEMP_DIR, url_hash(evicted)))
            except Exception as e:
                break

        PIHOME_LOGGER.info("Wallpaper Service: resizing wallpaper {} to fit in {}x{}".format(url, width, height))
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
        # self.current_color = "{}/{}".format(TEMP_DIR, colored)

        PIHOME_LOGGER.info("Wallpaper Service: resizing wallpaper {} complete and located in {}".format(url, TEMP_DIR))
        return "{}/{}".format(TEMP_DIR, resized), "{}/{}".format(TEMP_DIR, colored)

    def find_average_color(self, url):
        PIHOME_LOGGER.info("Wallpaper Service: finding average color for {}".format(url))
        r = requests.get(url)
        pilImage = PILImage.open(BytesIO(r.content), formats=("png", "jpeg"))
        pilImage = pilImage.resize((1, 1), PIL.Image.LANCZOS)
        PIHOME_LOGGER.info("Wallpaper Service: finding average color for {} complete".format(url))
        PIHOME_LOGGER.info("Wallpaper Service: average color is {}".format(pilImage.getpixel((0, 0))))
        return pilImage.getpixel((0, 0))

    def _cleanup(self):
        # remove any tmp file with _rsz or _color in the name
        for file in os.listdir(TEMP_DIR):
            if file.startswith("_rsz") or file.startswith("_color"):
                os.remove("{}/{}".format(TEMP_DIR, file))
        self.url_cache = []

    def ban_url(self, url, shuffle = False):
        self.ban_list.append(url)
        if shuffle:
            self.shuffle()
        self.serialize_ban_list()
        PIHOME_LOGGER.info("Wallpaper Service: banned url {}".format(url))

    def ban(self):
        self.ban_url(self.source, True)
        SFX.play("trash")

    def _apply_wallpaper(self, url):
        """
        Run resize_image on a background thread so blocking HTTP requests
        don't stall the GPIO interrupt thread (or any other caller).
        Once resizing is done, _reload_background is called which marshals
        the texture update back onto the Kivy main thread via Clock.
        """
        def _worker():
            self.current, self.current_color = self.resize_image(url, 1024, 1024)
            self.source = url
            get_app()._reload_background()

        PIHOME_LOGGER.info("Wallpaper Service: applying wallpaper {}".format(url))
        threading.Thread(target=_worker, daemon=True).start()

    def _pick_random_url_from_source(self):
        """
        Pick a random URL directly from the raw source batch cache (self.cache).
        This works regardless of how many images have been previously processed,
        making shuffle() functional from the very first press.
        """
        try:
            if self.repo == "Reddit" and self.cache:
                children = self.cache["data"]["children"]
                url = None
                attempts = 0
                while attempts < 20:
                    rand_idx = random.randint(0, len(children) - 1)
                    url = children[rand_idx]["data"]["url"]
                    if not url.endswith(".gif") and url not in self.ban_list:
                        return url
                    attempts += 1
            elif self.repo == "Wallhaven" and self.cache:
                data = self.cache["data"]
                url = None
                attempts = 0
                while attempts < 20:
                    rand_idx = random.randint(0, len(data) - 1)
                    url = data[rand_idx]["path"]
                    if not url.endswith(".gif"):
                        return url
                    attempts += 1
            elif self.repo == "Custom" and self.cache:
                return self.cache.get("img", None)
        except Exception as e:
            PIHOME_LOGGER.error(f"Wallpaper Service: error picking random url from source: {e}")
        return None

    def shuffle(self):
        # Prefer a random pick from url_cache (already-processed local images)
        PIHOME_LOGGER.info("Wallpaper Service: shuffling wallpaper")
        if len(self.url_cache) > 1:
            url = self.get_random_from_cache()
            if url and url != self.source:
                self._apply_wallpaper(url)
                return
        # Fall back to picking directly from the source batch cache
        url = self._pick_random_url_from_source()
        if url is None:
            toast("No wallpapers in cache to shuffle.  Please wait until more wallpapers are downloaded", "warn")
            return
        if url == self.source:
            # Try once more to get a different one
            url = self._pick_random_url_from_source() or url
        self._apply_wallpaper(url)

    def previous(self):
        # If url_cache too small to navigate sequentially, fall back to random pick
        PIHOME_LOGGER.info("Wallpaper Service: going to previous wallpaper")
        if len(self.url_cache) <= 1:
            url = self._pick_random_url_from_source()
            if url is None:
                toast("No wallpapers in cache to shuffle.  Please wait until more wallpapers are downloaded", "warn")
                return
            self._apply_wallpaper(url)
            return
        if self.shuffle_index >= len(self.url_cache) - 1:
            self.shuffle_index = 0
        else:
            self.shuffle_index += 1
        # FIX: was self.cache (raw JSON dict) — must use self.url_cache (list of URLs)
        url = self.url_cache[self.shuffle_index]
        if url is None:
            toast("No wallpaper found in cache", "error")
            return
        self._apply_wallpaper(url)

    def next(self):
        # If url_cache too small to navigate sequentially, fall back to random pick
        PIHOME_LOGGER.info("Wallpaper Service: going to next wallpaper")
        if len(self.url_cache) <= 1:
            url = self._pick_random_url_from_source()
            if url is None:
                toast("No wallpapers in cache to shuffle.  Please wait until more wallpapers are downloaded", "warn")
                return
            self._apply_wallpaper(url)
            return
        if self.shuffle_index <= 0:
            self.shuffle_index = len(self.url_cache) - 1
        else:
            self.shuffle_index -= 1
        # FIX: was self.cache (raw JSON dict) — must use self.url_cache (list of URLs)
        url = self.url_cache[self.shuffle_index]
        if url is None:
            toast("No wallpaper found in cache", "error")
            return
        self._apply_wallpaper(url)

    def get_random_from_cache(self):
        random_idx = random.randint(0, len(self.url_cache) - 1)
        return self.url_cache[random_idx]


WALLPAPER_SERVICE = Wallpaper()