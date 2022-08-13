from kivy.lang import Builder
from interface.gesturewidget import GestureWidget
from services.qr.qr import QR
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.animation import Animation
from kivy.clock import Clock
from util.const import GESTURE_SWIPE_DOWN
from util.helpers import get_config, get_poller

Builder.load_file("./composites/Reddit/redditwidget.kv")

class RedditWidget(GestureWidget):

    theme = Theme()
    background_color = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY, 0.5))
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    text_color_secondary = ColorProperty(theme.get_color(theme.TEXT_SECONDARY))

    content_opacity = NumericProperty(0)
    opacity = NumericProperty(0)
    background_image_opacity = NumericProperty(0)

    thumbnail = StringProperty("./assets/images/blank.png")
    qr = StringProperty("./assets/images/blank.png")
    title = StringProperty("")
    guilded = BooleanProperty(False)
    clicked = BooleanProperty(False)
    text = StringProperty("")
    source = StringProperty("")

    background_image = StringProperty("")

    qr_enabled = True
    item = 0
    item_max = 10
    data = None
    def __init__(self, **kwargs):
        super(RedditWidget, self).__init__(**kwargs)
        source = get_config().get("news", "source", "Disabled News")
        if source == "Disabled News":
            return

        subs = get_config().get("news", "subreddits", "politics+worldnews")
        if subs == "":
            subs = "politics"
        reddit_url = "https://www.reddit.com/r/{}.json?limit=100".format(subs)
        get_poller().register_api(reddit_url, 60 * 10, lambda json: self.parse_reddit(json));
        Clock.schedule_interval(lambda _: self.next(), 120)
        Clock.schedule_once(lambda _: self.start(), 20)

        self.on_gesture = self.handle_gesture
        self.on_click = self.handle_click

    def start(self):
        animation = Animation(opacity=1, t='linear', d=1)
        animation.start(self)
        self.next()


    def parse_reddit(self, json):
        self.data = json

    def fade_out(self, callback):
        animation = Animation(content_opacity=0, t='linear', d=1)
        animation.on_complete = lambda _: callback()
        animation.start(self)

    def fade_in(self):
        animation = Animation(content_opacity=1, t='linear', d=1)
        animation.start(self)

    def next(self):
        self.clicked = False
        self.fade_out(self._next)

    def _next(self):
        if self.data is None:
            return
        post = self.data["data"]["children"][self.item]["data"]
        self.title = post["title"]
        self.guilded= post["total_awards_received"] > 0
        self.source = post["domain"]
        thumbnail = post["thumbnail"]
        url = post["url"]
        if self.qr_enabled:
            self.qr = QR().from_url(url)
        if thumbnail.endswith(".jpg") or thumbnail.endswith(".png"):
            self.thumbnail = thumbnail
        else:
            self.thumbnail = "./assets/images/blank.png"

        if url.endswith(".jpg") or url.endswith(".png"):
            self.background_image = url
            self.background_image_opacity = 1
        else:
            self.background_image = ""
            self.background_image_opacity = 0

        self.item = self.item + 1
        if self.item > self.item_max:
            self.item = 0
        self.fade_in()

    def handle_gesture(self, gesture):
        if gesture == GESTURE_SWIPE_DOWN:
            self.next()
    
    def handle_click(self):
        self.clicked = not self.clicked