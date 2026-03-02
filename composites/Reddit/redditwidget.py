import json
from kivy.lang import Builder
from components.Image.networkimage import BLANK_IMAGE, LOGO_IMAGE
from composites.Reddit.redditpost import RedditPostOverlay
from interface.gesturewidget import GestureWidget
from networking.poller import POLLER
from services.qr.qr import QR
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from util.configuration import CONFIG
from util.const import GESTURE_SWIPE_DOWN
from util.phlog import PIHOME_LOGGER

Builder.load_file("./composites/Reddit/redditwidget.kv")

class RedditWidget(GestureWidget):

    theme = Theme()
    background_color = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY, 0.4))
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    text_color_secondary = ColorProperty(theme.get_color(theme.TEXT_SECONDARY))

    accent_color = ColorProperty(theme.get_color(theme.ALERT_INFO))
    card_bg_color = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY, 1.0))

    content_opacity = NumericProperty(0)
    background_image_opacity = NumericProperty(0)

    thumbnail = StringProperty(BLANK_IMAGE)
    qr = StringProperty(BLANK_IMAGE)
    title = StringProperty("")
    guilded = BooleanProperty(False)
    clicked = BooleanProperty(False)
    source = StringProperty("")
    subreddit_label = StringProperty("")
    upvotes_label = StringProperty("")
    comment_count_label = StringProperty("")
    flair_text_label = StringProperty("")

    background_image = StringProperty("")

    qr_enabled = True
    item = 0
    data = None
    _started = False
    _current_post = None

    def __init__(self, **kwargs):
        super(RedditWidget, self).__init__(**kwargs)
        self._poller_key = None
        self._clock_next = None
        self._touch_start = None
        self.on_gesture = self.handle_gesture
        self.on_click = self.handle_click

        source = CONFIG.get("news", "source", "Disabled News")
        if source == "Disabled News":
            self.opacity = 0
            return

        self._active_subs = CONFIG.get("news", "subreddits", "politics+worldnews")
        self.opacity = 0
        self._start_feed()

    def _start_feed(self, start_delay=20):
        subs = CONFIG.get("news", "subreddits", "politics+worldnews")
        if subs == "":
            subs = "politics"
        # reddit_url = "https://www.reddit.com/r/{}.json?limit=100".format(subs)
        reddit_url = "https://imotbo.com/r.php?sub=/r/{}/hot&limit=8&ttime=all&after=8".format(subs)
        PIHOME_LOGGER.info("RedditWidget: starting feed from {}".format(reddit_url))
        self._poller_key = POLLER.register_api(reddit_url, 60 * 10, lambda data: self.parse_reddit(data))
        self._clock_next = Clock.schedule_interval(lambda _: self.next(), 120)
        Clock.schedule_once(lambda _: self.start(), start_delay)
        # Safety net: if still blank after start_delay+10s, force a display attempt
        Clock.schedule_once(lambda _: self._force_show_if_blank(), start_delay + 10)

    def _stop_feed(self):
        if self._poller_key is not None:
            POLLER.unregister_api(self._poller_key)
            self._poller_key = None
        if self._clock_next is not None:
            self._clock_next.cancel()
            self._clock_next = None
        self.data = None
        self.item = 0
        self._started = False

    def on_config_update(self, config):
        source = CONFIG.get("news", "source", "Disabled News")
        if source == "Disabled News":
            self._stop_feed()
            self.opacity = 0
            return

        new_subs = CONFIG.get("news", "subreddits", "politics+worldnews")
        if self._poller_key is None:
            # Feed wasn't running — start fresh
            self._active_subs = new_subs
            self._start_feed(start_delay=2)
        elif new_subs != self._active_subs:
            # Subreddits changed — tear down old feed and reload
            PIHOME_LOGGER.info("RedditWidget: subreddits changed to '{}', restarting feed".format(new_subs))
            self._active_subs = new_subs
            self._stop_feed()
            self.content_opacity = 0
            self._start_feed(start_delay=2)

            
    def start(self):
        PIHOME_LOGGER.info("RedditWidget: start() fired, data={}".format(
            "available ({} posts)".format(len(self.data["data"]["children"])) if self.data else "None"))
        self._started = True
        self.next()

    def _force_show_if_blank(self):
        """Safety net: called at t+30s. If the widget is still blank, force a display attempt."""
        if self.content_opacity == 0 and self.data is not None:
            PIHOME_LOGGER.warn("RedditWidget: still blank at 30s, forcing display")
            self._next()
        elif self.data is None:
            PIHOME_LOGGER.error("RedditWidget: still blank at 30s and no data — API may have failed")


    def parse_reddit(self, raw):
        was_none = self.data is None
        # UrlRequest only auto-parses JSON when Content-Type is application/json.
        # The proxy may return a plain string — decode it manually if needed.
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception as e:
                PIHOME_LOGGER.error("RedditWidget: failed to decode JSON: {}".format(e))
                return
        if not isinstance(raw, dict):
            PIHOME_LOGGER.error("RedditWidget: unexpected data type: {}".format(type(raw)))
            return
        self.data = raw
        PIHOME_LOGGER.info("RedditWidget: received {} posts".format(
            len(self.data.get("data", {}).get("children", []))))
        # If start() has already fired but _next() returned early because data
        # was None at that point, trigger a display cycle now.
        if was_none and self._started and self.content_opacity == 0:
            self._next()

    def fade_out(self, callback):
        animation = Animation(content_opacity=0, t='linear', d=0.4)
        animation.on_complete = lambda _: callback()
        animation.start(self)

    def fade_in(self):
        # On first call opacity is 0 (hidden during intro); animate both together.
        # On subsequent calls opacity is already 1 so only content_opacity changes.
        animation = Animation(opacity=1, t='out_quad', d=0.8)
        animation &= Animation(content_opacity=1, t='linear', d=0.6)
        animation.start(self)

    def next(self):
        self.clicked = False
        self.fade_out(self._next)

    def _format_count(self, n):
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.1f}k"
        return str(n)

    def _next(self):
        if self.data is None:
            PIHOME_LOGGER.warn("RedditWidget: _next called but data is None")
            return
        try:
            children = self.data["data"]["children"]
        except (KeyError, TypeError) as e:
            PIHOME_LOGGER.error("RedditWidget: bad data structure: {} — data={}".format(e, str(self.data)[:200]))
            return
        if not children:
            PIHOME_LOGGER.warn("RedditWidget: children list is empty")
            return
        if self.item >= len(children):
            self.item = 0
        post = children[self.item]["data"]
        PIHOME_LOGGER.info("RedditWidget: displaying item {}/{}: {}".format(
            self.item, len(children), post.get("title", "")[:60]))

        try:
          self._populate(post)
        except Exception as e:
            PIHOME_LOGGER.error("RedditWidget: exception in _populate: {}".format(e))
            return
        self.item = (self.item + 1) % len(children)
        self.fade_in()

    def _populate(self, post):
        self._current_post = post
        self.title = post.get("title", "")
        self.guilded = post.get("total_awards_received", 0) > 0
        self.source = post.get("domain", "")
        self.subreddit_label = post.get("subreddit_name_prefixed", "")
        self.upvotes_label = self._format_count(post.get("ups") or post.get("score") or 0)
        self.comment_count_label = self._format_count(post.get("num_comments", 0))
        self.flair_text_label = post.get("link_flair_text") or ""

        thumbnail = post.get("thumbnail", "")
        url = post.get("url", "")
        if self.qr_enabled:
            self.qr = QR().from_url(url)
        if thumbnail and (thumbnail.endswith(".jpg") or thumbnail.endswith(".png")):
            self.thumbnail = thumbnail
        else:
            self.thumbnail = LOGO_IMAGE

        try:
            preview_url = post["preview"]["images"][0]["source"]["url"].replace("&amp;", "&")
            self.background_image = preview_url
            self.background_image_opacity = 1
        except (KeyError, IndexError, TypeError):
            self.background_image = ""
            self.background_image_opacity = 0

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_start = (touch.x, touch.y)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self._touch_start is not None:
            dx = abs(touch.x - self._touch_start[0])
            dy = abs(touch.y - self._touch_start[1])
            # Only treat as a tap if the finger/cursor barely moved
            if dx < dp(20) and dy < dp(20):
                self.handle_click()
        self._touch_start = None
        return super().on_touch_up(touch)

    def handle_gesture(self, gesture):
        if gesture == GESTURE_SWIPE_DOWN:
            self.next()
    
    def handle_click(self):
        if self._current_post is not None:
            RedditPostOverlay.open(self._current_post)