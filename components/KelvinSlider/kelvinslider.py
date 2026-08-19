"""Horizontal colour-temperature slider, warm to cool.

The track is a blackbody gradient so the control shows what it does.  Touch or
drag anywhere on it to pick a temperature; the widget dispatches
``on_kelvin_pick(kelvin)`` rather than mutating its own ``kelvin`` property, so
the parent stays the single source of truth (same contract as ColorWheel).

The gradient is generated once for the full 1500-9000K range and cached on the
class.  A narrower per-bulb range samples a slice of that texture through
``tex_coords`` instead of rebuilding it, so switching selection costs nothing.

Sizing is left to the caller - set ``size_hint_y: None`` and a ``height`` at
the usage site.
"""

from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.properties import ColorProperty, NumericProperty
from kivy.uix.widget import Widget

from screens.LIFX.protocol import KELVIN_MAX, KELVIN_MIN, kelvin_to_rgb

try:
    import numpy as np
    _NUMPY = True
except ImportError:      # pragma: no cover
    _NUMPY = False

_GRAD_STEPS = 256
_STEP_K = 50             # snap resolution: finer than anyone can see
_THUMB = dp(22)


class KelvinSlider(Widget):

    kelvin = NumericProperty(3500)
    min_kelvin = NumericProperty(KELVIN_MIN)
    max_kelvin = NumericProperty(KELVIN_MAX)

    track_height = NumericProperty(dp(26))
    thumb_color = ColorProperty([1, 1, 1, 0.95])
    border_color = ColorProperty([1, 1, 1, 0.14])

    __events__ = ("on_kelvin_pick",)

    _shared_tex = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tex = self._texture()
        self.bind(size=self._redraw, pos=self._redraw, kelvin=self._redraw,
                  min_kelvin=self._redraw, max_kelvin=self._redraw,
                  track_height=self._redraw, thumb_color=self._redraw)
        self._redraw()

    # ── Gradient texture (once per process) ───────────────────────────────

    @classmethod
    def _texture(cls):
        if cls._shared_tex is None:
            tex = Texture.create(size=(_GRAD_STEPS, 1), colorfmt="rgb")
            tex.blit_buffer(cls._build_gradient(), colorfmt="rgb",
                            bufferfmt="ubyte")
            tex.wrap = "clamp_to_edge"
            tex.min_filter = "linear"
            tex.mag_filter = "linear"
            cls._shared_tex = tex
        return cls._shared_tex

    @staticmethod
    def _build_gradient():
        """The full KELVIN_MIN..KELVIN_MAX ramp as RGB bytes."""
        span = KELVIN_MAX - KELVIN_MIN
        colors = [
            kelvin_to_rgb(KELVIN_MIN + span * i / float(_GRAD_STEPS - 1))
            for i in range(_GRAD_STEPS)
        ]
        if _NUMPY:
            return np.array(colors, dtype=np.uint8).tobytes()
        buf = bytearray()
        for rgb in colors:
            buf.extend(rgb)
        return bytes(buf)

    def _tex_coords(self):
        """Sample only the sub-range this selection actually supports."""
        span = float(KELVIN_MAX - KELVIN_MIN)
        low = (self._low() - KELVIN_MIN) / span
        high = (self._high() - KELVIN_MIN) / span
        if high <= low:
            high = min(1.0, low + 1.0 / _GRAD_STEPS)
        return (low, 0.0, high, 0.0, high, 1.0, low, 1.0)

    # ── Range helpers ─────────────────────────────────────────────────────

    def _low(self):
        return max(KELVIN_MIN, min(self.min_kelvin, self.max_kelvin))

    def _high(self):
        return min(KELVIN_MAX, max(self.min_kelvin, self.max_kelvin))

    def _usable(self):
        return max(self.width - _THUMB, 1.0)

    def _fraction(self):
        low, high = self._low(), self._high()
        if high <= low:
            return 0.5
        return max(0.0, min(1.0, (self.kelvin - low) / float(high - low)))

    def _x_to_kelvin(self, x):
        low, high = self._low(), self._high()
        rel = (x - self.x - _THUMB / 2.0) / self._usable()
        rel = max(0.0, min(1.0, rel))
        raw = low + rel * (high - low)
        snapped = int(round(raw / _STEP_K) * _STEP_K)
        return max(low, min(high, snapped))

    def _kelvin_to_x(self):
        """Left edge of the thumb."""
        return self.x + self._fraction() * self._usable()

    # ── Drawing ───────────────────────────────────────────────────────────

    def _redraw(self, *args):
        self.canvas.clear()
        track_h = max(dp(6), self.track_height)
        track_y = self.center_y - track_h / 2.0
        radius = track_h / 2.0
        thumb_x = self._kelvin_to_x()

        with self.canvas:
            Color(1, 1, 1, 1)
            RoundedRectangle(
                texture=self._tex,
                tex_coords=self._tex_coords(),
                pos=(self.x, track_y),
                size=(self.width, track_h),
                radius=[radius],
            )

            # Hairline so a pale warm track still reads as a control on a
            # light background.
            Color(*self.border_color)
            RoundedRectangle(
                pos=(self.x, track_y),
                size=(self.width, dp(1)),
                radius=[dp(0.5)],
            )

            Color(0, 0, 0, 0.20)
            Ellipse(pos=(thumb_x + dp(1), self.center_y - dp(10)),
                    size=(dp(20), dp(20)))

            Color(*self.thumb_color)
            Ellipse(pos=(thumb_x, self.center_y - dp(11)),
                    size=(_THUMB, _THUMB))

            # Fill the thumb with the temperature it currently sits on.
            red, green, blue = kelvin_to_rgb(self.kelvin)
            Color(red / 255.0, green / 255.0, blue / 255.0, 1)
            Ellipse(pos=(thumb_x + dp(4), self.center_y - dp(7)),
                    size=(dp(14), dp(14)))

    # ── Touch ─────────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        touch.grab(self)
        # Without this, PiHomeScreen.touch_up reads the horizontal drag as a
        # navigation swipe and slides the screen away mid-adjust.
        touch.ud['ph_control_touch'] = True
        self.dispatch("on_kelvin_pick", self._x_to_kelvin(touch.x))
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.dispatch("on_kelvin_pick", self._x_to_kelvin(touch.x))
            return True
        return False

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.dispatch("on_kelvin_pick", self._x_to_kelvin(touch.x))
            return True
        return False

    def on_kelvin_pick(self, kelvin):
        """Default handler - the parent binds this."""
        pass
