from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from components.Button.circlebutton import CircleButton
from theme.color import Color
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from util.helpers import get_app, get_config, get_poller
from util.tools import hex
from kivy.uix.widget import Widget

Builder.load_file("./composites/Reddit/redditwidget.kv")

class RedditWidget(Widget):

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
    text = StringProperty("")
    source = StringProperty("")

    background_image = StringProperty("")

    qr_api = "https://api.qrserver.com/v1/create-qr-code/?size=100x100&data="
    qr_enabled = False
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
            self.qr = self.qr_api + url
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

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.next()
            return False