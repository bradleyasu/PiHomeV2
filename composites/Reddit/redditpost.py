import json
import time as time_module

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.network.urlrequest import UrlRequest
from kivy.properties import (BooleanProperty, ColorProperty, NumericProperty,
                              StringProperty)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label

from components.Image.networkimage import BLANK_IMAGE, NetworkImage
from components.Switch.switch import PiHomeSwitch  # noqa: F401 — registers rule
from services.qr.qr import QR
from theme.theme import Theme
from util.phlog import PIHOME_LOGGER

Builder.load_file("./composites/Reddit/redditpost.kv")

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

# Accent colours cycling by comment depth
DEPTH_COLORS = [
    [0.36, 0.67, 1.00, 1.0],   # blue
    [0.43, 0.86, 0.58, 1.0],   # green
    [1.00, 0.70, 0.30, 1.0],   # orange
    [0.80, 0.50, 1.00, 1.0],   # purple
    [0.45, 0.85, 0.85, 1.0],   # teal
]


def _fmt(n):
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}k"
        return str(n)
    except Exception:
        return "0"


def _rel_time(utc):
    try:
        diff = time_module.time() - float(utc)
        if diff < 60:
            return "just now"
        if diff < 3600:
            return f"{int(diff//60)}m"
        if diff < 86400:
            return f"{int(diff//3600)}h"
        return f"{int(diff//86400)}d"
    except Exception:
        return ""


def _flatten(children, depth=0, out=None):
    """Recursively flatten Reddit comment tree into list of dicts with depth."""
    if out is None:
        out = []
    for child in children:
        if child.get("kind") != "t1":
            continue
        d = child["data"]
        body = d.get("body", "").strip()
        if body and body not in ("[deleted]", "[removed]"):
            out.append({
                "depth":        min(depth, 8),      # cap visual indent
                "author":       d.get("author", "[deleted]"),
                "score":        d.get("score", 0),
                "utc":          d.get("created_utc", 0),
                "author_flair": d.get("author_flair_text") or "",
                "body":         body,
            })
        replies = d.get("replies")
        if isinstance(replies, dict):
            _flatten(replies.get("data", {}).get("children", []), depth + 1, out)
    return out


# ----------------------------------------------------------------------------
# RedditCommentCard
# ----------------------------------------------------------------------------

class RedditCommentCard(BoxLayout):
    """Single comment row: depth-indented with a coloured left accent bar."""
    depth        = NumericProperty(0)
    author       = StringProperty("")
    score_label  = StringProperty("")
    time_label   = StringProperty("")
    author_flair = StringProperty("")
    body         = StringProperty("")
    accent_color = ColorProperty([0.36, 0.67, 1.0, 1.0])
    text_color   = ColorProperty([1, 1, 1, 0.88])
    bg_color     = ColorProperty([1, 1, 1, 0.04])

    def __init__(self, depth=0, author="", score=0, utc=0,
                 author_flair="", body="", **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        # Left padding grows with depth to show threading
        self.padding = [dp(14 + depth * 14), dp(8), dp(12), dp(6)]
        self.spacing = dp(2)

        self.depth = depth
        self.author = author
        self.score_label = _fmt(score) + " pts"
        self.time_label = _rel_time(utc)
        self.author_flair = author_flair
        self.body = body
        self.accent_color = DEPTH_COLORS[depth % len(DEPTH_COLORS)]

        t = Theme()
        self.text_color = t.get_color(t.TEXT_PRIMARY)
        self.bg_color = [1, 1, 1, 0.06 if depth % 2 == 0 else 0.03]

        # Auto-height after layout pass
        self.bind(minimum_height=self.setter("height"))


# ----------------------------------------------------------------------------
# RedditPostOverlay
# ----------------------------------------------------------------------------

class RedditPostOverlay(FloatLayout):
    """Full-screen overlay: post title, body/image, threaded comments."""
    theme = Theme()

    title           = StringProperty("")
    body            = StringProperty("")
    author          = StringProperty("")
    subreddit_label = StringProperty("")
    score_label     = StringProperty("")
    num_comments    = StringProperty("")
    post_url        = StringProperty("")
    permalink       = StringProperty("")
    image_url       = StringProperty("")
    is_image        = BooleanProperty(False)
    qr_url          = StringProperty(BLANK_IMAGE)
    show_qr         = BooleanProperty(False)
    show_comments   = BooleanProperty(False)
    loading         = BooleanProperty(False)
    comment_count   = NumericProperty(0)

    card_color    = ColorProperty([0.07, 0.09, 0.13, 0.98])
    text_color    = ColorProperty([1, 1, 1, 0.90])
    accent_color  = ColorProperty([0.36, 0.67, 1.0, 1.0])
    divider_color = ColorProperty([1, 1, 1, 0.10])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = Window.size
        self.pos = (0, 0)
        t = Theme()
        self.text_color  = t.get_color(t.TEXT_PRIMARY)
        self.accent_color = t.get_color(t.ALERT_INFO)

    def on_touch_down(self, touch):
        # Consume all touches so widgets behind the overlay never receive them
        super().on_touch_down(touch)
        return True

    def on_touch_up(self, touch):
        super().on_touch_up(touch)
        return True

    def on_touch_move(self, touch):
        super().on_touch_move(touch)
        return True

    # ── Public API ──────────────────────────────────────────────────────────

    def load(self, post_data):
        """Populate from a Reddit post dict then kick off comment fetch."""
        self.title           = post_data.get("title", "")
        self.body            = (post_data.get("selftext") or "").strip()
        self.author          = "/u/" + post_data.get("author", "")
        self.subreddit_label = post_data.get("subreddit_name_prefixed", "")
        self.score_label     = _fmt(post_data.get("ups") or post_data.get("score") or 0)
        self.num_comments    = _fmt(post_data.get("num_comments", 0)) + " comments"
        self.post_url        = post_data.get("url", "")
        self.permalink       = post_data.get("permalink", "")
        try:
            self.qr_url = QR().from_url(self.post_url)
        except Exception:
            pass

        # Decide image vs body
        url_lower = self.post_url.lower()
        is_img = url_lower.endswith((".jpg", ".jpeg", ".png", ".webp"))
        if not is_img:
            try:
                preview = post_data["preview"]["images"][0]["source"]["url"].replace("&amp;", "&")
                if not preview.lower().endswith(".gif"):
                    self.image_url = preview
                    is_img = True
            except (KeyError, IndexError, TypeError):
                pass
        if is_img and not url_lower.endswith(".gif"):
            if not self.image_url:
                self.image_url = self.post_url
            self.is_image = True
        else:
            self.is_image = False

        Clock.schedule_once(lambda dt: self._setup_post_content(), 0.1)
        self.fetch_comments()

    def fetch_comments(self):
        if not self.permalink:
            return
        self._clear_comments()
        self.loading = True
        api_url = "https://imotbo.com/r.php?sub={}".format(self.permalink)
        PIHOME_LOGGER.info("RedditPostOverlay: fetching {}".format(api_url))
        UrlRequest(
            api_url,
            on_success=self._on_success,
            on_failure=self._on_error,
            on_error=self._on_error,
            timeout=20,
        )

    def toggle_qr(self):
        self.show_qr = not self.show_qr

    def close(self):
        anim = Animation(opacity=0, t="linear", d=0.2)
        anim.bind(on_complete=lambda *_: Window.remove_widget(self))
        anim.start(self)

    @staticmethod
    def open(post_data):
        """Create overlay, add to Window, animate in, load data."""
        overlay = RedditPostOverlay()
        overlay.opacity = 0
        Window.add_widget(overlay)
        Animation(opacity=1, t="out_quad", d=0.25).start(overlay)
        overlay.load(post_data)
        return overlay

    # ── Private ─────────────────────────────────────────────────────────────

    def _setup_post_content(self):
        """Add image or body-text widget to the post_body_area shell."""
        from kivy.uix.scrollview import ScrollView as KivyScrollView
        area = self.ids.get("post_body_area")
        if area is None:
            return
        area.clear_widgets()
        if self.is_image and self.image_url:
            img = NetworkImage(
                url=self.image_url,
                size_hint=(1, 1),
                enable_stretch=False,
            )
            area.add_widget(img)
        elif self.body:
            sv = KivyScrollView(
                size_hint=(1, 1),
                do_scroll_x=False,
                bar_width=dp(3),
                bar_color=self.accent_color,
                scroll_type=['bars', 'content'],
            )
            lbl = Label(
                text=self.body,
                color=self.text_color,
                font_size='14sp',
                font_name='Nunito',
                size_hint_x=1,
                size_hint_y=None,
                halign='left',
                valign='top',
            )
            # Bind text_size to label width so wrapping works, then sync height
            lbl.bind(
                width=lambda lbl, w: setattr(lbl, 'text_size', (w, None)),
                texture_size=lambda lbl, ts: setattr(lbl, 'height', ts[1]),
            )
            sv.add_widget(lbl)
            area.add_widget(sv)
            # Force text_size once the widget has a real width after layout
            Clock.schedule_once(
                lambda dt: setattr(lbl, 'text_size', (lbl.width, None)), 0.1
            )

    def _on_success(self, req, result):
        self.loading = False
        try:
            if isinstance(result, str):
                result = json.loads(result)
            if isinstance(result, list) and len(result) >= 2:
                children = result[1]["data"]["children"]
            elif isinstance(result, dict):
                children = result.get("data", {}).get("children", [])
            else:
                children = []
            self._populate_comments(_flatten(children))
        except Exception as e:
            PIHOME_LOGGER.error("RedditPostOverlay: parse error: {}".format(e))

    def _on_error(self, req, error):
        self.loading = False
        PIHOME_LOGGER.error("RedditPostOverlay: fetch error: {}".format(error))

    def _populate_comments(self, flat):
        container = self.ids.get("comments_container")
        if container is None:
            PIHOME_LOGGER.error("RedditPostOverlay: comments_container id not found")
            return
        container.clear_widgets()
        for c in flat:
            card = RedditCommentCard(
                depth=c["depth"],
                author=c["author"],
                score=c["score"],
                utc=c["utc"],
                author_flair=c["author_flair"],
                body=c["body"],
            )
            container.add_widget(card)
        self.comment_count = len(flat)
        # Force a layout pass now that all cards have been added
        Clock.schedule_once(lambda dt: container.do_layout(), 0.05)

    def _clear_comments(self):
        container = self.ids.get("comments_container")
        if container:
            container.clear_widgets()
        self.comment_count = 0
