"""Custom widgets for the Spotify screen.

All classes are self-contained — no PiHome imports beyond Kivy.
"""
from kivy.animation import Animation
from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty, ColorProperty, NumericProperty, StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget


# ── Slim custom slider ────────────────────────────────────────────────────────

class SpotifySlider(Widget):
    """Thin pill-track slider with a colored fill and animated dot thumb.

    Properties
    ----------
    min_val / max_val   range
    value               current value (bindable, two-way)
    track_color         unfilled track color
    fill_color          filled (left) portion color
    thumb_color         draggable dot color
    track_height        dp height of the track pill
    thumb_r             radius of the thumb dot at rest
    """

    min_val      = NumericProperty(0.0)
    max_val      = NumericProperty(1.0)
    value        = NumericProperty(0.0)
    track_color  = ColorProperty([0.20, 0.20, 0.20, 1])
    fill_color   = ColorProperty([0.11, 0.73, 0.33, 1])
    thumb_color  = ColorProperty([1, 1, 1, 1])
    track_height = NumericProperty(dp(4))
    thumb_r      = NumericProperty(dp(7))
    _thumb_s     = NumericProperty(1.0)   # animated scale multiplier

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            pos=self._redraw, size=self._redraw,
            value=self._redraw, _thumb_s=self._redraw,
            track_color=self._redraw, fill_color=self._redraw,
            thumb_color=self._redraw,
        )

    @property
    def _frac(self):
        span = max(self.max_val - self.min_val, 1e-9)
        return max(0.0, min(1.0, (self.value - self.min_val) / span))

    def _redraw(self, *_):
        self.canvas.clear()
        th   = self.track_height
        tr   = self.thumb_r * self._thumb_s
        cy   = self.y + self.height / 2
        frac = self._frac
        fw   = frac * self.width

        with self.canvas:
            # Track
            Color(rgba=self.track_color)
            RoundedRectangle(
                pos=(self.x, cy - th / 2),
                size=(self.width, th),
                radius=[th / 2],
            )
            # Fill
            if fw > 0:
                Color(rgba=self.fill_color)
                RoundedRectangle(
                    pos=(self.x, cy - th / 2),
                    size=(fw, th),
                    radius=[th / 2],
                )
            # Thumb dot
            Color(rgba=self.thumb_color)
            Ellipse(
                pos=(self.x + fw - tr, cy - tr),
                size=(tr * 2, tr * 2),
            )

    # Touch handling ──────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self._set_from_touch(touch)
            Animation(_thumb_s=1.45, d=0.10, t="out_quad").start(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self._set_from_touch(touch)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            Animation(_thumb_s=1.0, d=0.18, t="out_quad").start(self)
            return True
        return super().on_touch_up(touch)

    def _set_from_touch(self, touch):
        frac = (touch.x - self.x) / max(self.width, 1)
        self.value = self.min_val + max(0.0, min(1.0, frac)) * (
            self.max_val - self.min_val
        )


# ── Image-based icon button ───────────────────────────────────────────────────

class SpotifyIconButton(ButtonBehavior, Image):
    """PNG icon button with a spring-scale press animation.

    Pass ``source`` (path to PNG), ``size=(w, h)``.
    Bind ``on_press`` for action.
    """

    _bw = NumericProperty(0)
    _bh = NumericProperty(0)

    def __init__(self, **kwargs):
        kwargs.setdefault("allow_stretch", True)
        kwargs.setdefault("keep_ratio", True)
        kwargs.setdefault("size_hint", (None, None))
        super().__init__(**kwargs)
        self.bind(size=self._capture_base)

    def _capture_base(self, inst, val):
        if not self._bw:
            self._bw, self._bh = val

    def on_press(self):
        if self._bw:
            Animation(
                size=(self._bw * 0.80, self._bh * 0.80),
                d=0.08, t="out_quad",
            ).start(self)

    def on_release(self):
        if self._bw:
            Animation(
                size=(self._bw, self._bh),
                d=0.24, t="out_back",
            ).start(self)


# ── Text-only toggle button (shuffle / repeat) ────────────────────────────────

class SpotifyTextButton(ButtonBehavior, Label):
    """Label that acts as a pressable toggle.

    Set ``active`` to True/False to switch between active_color / idle_color.
    Use ``ArialUnicode`` font for unicode symbol support.
    """

    active       = BooleanProperty(False)
    active_color = ColorProperty([0.11, 0.73, 0.33, 1])
    idle_color   = ColorProperty([1, 1, 1, 0.40])
    _opacity_anim = NumericProperty(1.0)

    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", "ArialUnicode")
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        super().__init__(**kwargs)
        self.bind(active=self._sync_color, _opacity_anim=self._apply_opacity)
        self._sync_color()

    def _sync_color(self, *_):
        base = self.active_color if self.active else self.idle_color
        self.color = list(base[:3]) + [base[3] * self._opacity_anim]

    def _apply_opacity(self, inst, v):
        self._sync_color()

    def on_press(self):
        Animation(_opacity_anim=0.5, d=0.06, t="out_quad").start(self)

    def on_release(self):
        Animation(_opacity_anim=1.0, d=0.20, t="out_quad").start(self)
