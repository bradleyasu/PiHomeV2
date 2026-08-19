"""HSV colour wheel widget.

Renders a circular HSV wheel as a pre-generated texture.  Touch to pick hue
(angle) and saturation (distance from centre).  A separate brightness value is
exposed as a property so the parent can bind a slider to it.

Touch interaction dispatches ``on_color_pick(hue, saturation)`` so the parent
can update its own state without fighting KV expression bindings.

Shared by the Nanoleaf and LIFX screens.  The texture is built once per
process and cached on the class - ``PihomeScreenManager.load_screens()``
instantiates every screen at boot, so a per-instance build would be paid on
startup by every screen that uses one.
"""

import colorsys
import math

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse
from kivy.graphics.texture import Texture
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.widget import Widget

try:
    import numpy as np
    _NUMPY = True
except ImportError:      # pragma: no cover - degrade rather than break two screens
    _NUMPY = False

_TEX_SIZE = 256   # wheel texture resolution (NxN)
_EDGE_PX = 1.5    # width of the alpha ramp that antialiases the rim


class ColorWheel(Widget):
    """Circular HSV colour picker.

    Properties ``hue``, ``saturation``, ``brightness`` can be set from outside
    (e.g. KV bindings) to display the current state.  When the user *touches*
    the wheel, ``on_color_pick`` is dispatched with the new (hue, saturation)
    values - the parent should handle that event and update its own properties
    which will flow back via KV bindings.
    """

    hue = NumericProperty(0)            # 0-360 degrees
    saturation = NumericProperty(100)   # 0-100
    brightness = NumericProperty(100)   # 0-100  (V in HSV)
    selected_color = ListProperty([255, 0, 0])  # RGB 0-255 (includes brightness)

    __events__ = ("on_color_pick",)

    _shared_tex = None   # class level: one texture for every instance

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._wheel_tex = self._texture()
        self.bind(size=self._redraw, pos=self._redraw,
                  hue=self._on_hsv_change, saturation=self._on_hsv_change,
                  brightness=self._on_hsv_change)
        Clock.schedule_once(lambda dt: self._redraw(), 0)

    # ── Texture generation (once per process) ─────────────────────────────

    @classmethod
    def _texture(cls):
        if cls._shared_tex is None:
            buf = cls._build_buffer_numpy() if _NUMPY else cls._build_buffer_python()
            tex = Texture.create(size=(_TEX_SIZE, _TEX_SIZE), colorfmt="rgba")
            tex.blit_buffer(buf, colorfmt="rgba", bufferfmt="ubyte")
            tex.flip_vertical()
            cls._shared_tex = tex
        return cls._shared_tex

    @staticmethod
    def _build_buffer_numpy():
        size = _TEX_SIZE
        centre = size / 2.0
        radius = size / 2.0

        yy, xx = np.mgrid[0:size, 0:size]
        dx = xx - centre
        dy = yy - centre
        dist = np.hypot(dx, dy)

        hue = (np.degrees(np.arctan2(dy, dx)) % 360.0) / 360.0
        sat = np.clip(dist / radius, 0.0, 1.0)

        # Vectorised HSV -> RGB at V = 1.
        i = np.floor(hue * 6.0)
        f = hue * 6.0 - i
        q = 1.0 - f * sat
        t = 1.0 - (1.0 - f) * sat
        p = 1.0 - sat
        ones = np.ones_like(hue)
        sector = (i % 6).astype(np.int8)

        red = np.select([sector == 0, sector == 1, sector == 2,
                         sector == 3, sector == 4, sector == 5],
                        [ones, q, p, p, t, ones])
        green = np.select([sector == 0, sector == 1, sector == 2,
                           sector == 3, sector == 4, sector == 5],
                          [t, ones, ones, q, p, p])
        blue = np.select([sector == 0, sector == 1, sector == 2,
                          sector == 3, sector == 4, sector == 5],
                         [p, p, t, ones, ones, q])

        # Soft rim: fade the last couple of pixels instead of a hard sawtooth.
        alpha = np.clip((radius - dist) / _EDGE_PX, 0.0, 1.0)
        # Zero the colour outside the disc too. With linear filtering a fully
        # transparent but *coloured* texel still bleeds its hue into the rim.
        mask = alpha > 0.0

        rgba = np.zeros((size, size, 4), dtype=np.uint8)
        rgba[..., 0] = np.where(mask, red * 255, 0).astype(np.uint8)
        rgba[..., 1] = np.where(mask, green * 255, 0).astype(np.uint8)
        rgba[..., 2] = np.where(mask, blue * 255, 0).astype(np.uint8)
        rgba[..., 3] = (alpha * 255).astype(np.uint8)
        return rgba.tobytes()

    @staticmethod
    def _build_buffer_python():
        size = _TEX_SIZE
        buf = bytearray(size * size * 4)
        centre = size / 2.0
        radius = size / 2.0

        for y in range(size):
            for x in range(size):
                dx = x - centre
                dy = y - centre
                dist = math.sqrt(dx * dx + dy * dy)
                idx = (y * size + x) * 4

                alpha = max(0.0, min(1.0, (radius - dist) / _EDGE_PX))
                if alpha <= 0.0:
                    buf[idx] = buf[idx + 1] = buf[idx + 2] = buf[idx + 3] = 0
                    continue

                angle = math.atan2(dy, dx)
                h = (math.degrees(angle) + 360) % 360 / 360.0
                s = min(1.0, dist / radius)
                r, g, b = colorsys.hsv_to_rgb(h, s, 1.0)
                buf[idx] = int(r * 255)
                buf[idx + 1] = int(g * 255)
                buf[idx + 2] = int(b * 255)
                buf[idx + 3] = int(alpha * 255)

        return bytes(buf)

    # ── Drawing ───────────────────────────────────────────────────────────

    def _redraw(self, *args):
        self.canvas.clear()
        if not self._wheel_tex:
            return

        s = min(self.width, self.height)
        cx = self.x + self.width / 2.0
        cy = self.y + self.height / 2.0

        with self.canvas:
            # Wheel
            Color(1, 1, 1, 1)
            Ellipse(
                texture=self._wheel_tex,
                pos=(cx - s / 2.0, cy - s / 2.0),
                size=(s, s),
            )

            # Selector dot
            self._draw_selector(cx, cy, s / 2.0)

    def _draw_selector(self, cx, cy, radius):
        angle_rad = math.radians(self.hue)
        dist = (self.saturation / 100.0) * radius
        sx = cx + dist * math.cos(angle_rad)
        sy = cy + dist * math.sin(angle_rad)

        # Black outer ring
        Color(0, 0, 0, 1)
        Ellipse(pos=(sx - 9, sy - 9), size=(18, 18))
        # White middle ring
        Color(1, 1, 1, 1)
        Ellipse(pos=(sx - 7, sy - 7), size=(14, 14))
        # Fill with the currently selected colour
        r, g, b = [c / 255.0 for c in self.selected_color]
        Color(r, g, b, 1)
        Ellipse(pos=(sx - 5, sy - 5), size=(10, 10))

    # ── Colour computation ────────────────────────────────────────────────

    def _on_hsv_change(self, *args):
        h = self.hue / 360.0
        s = self.saturation / 100.0
        v = self.brightness / 100.0
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        self.selected_color = [int(r * 255), int(g * 255), int(b * 255)]
        self._redraw()

    # ── Touch handling ────────────────────────────────────────────────────

    def _get_wheel_geometry(self):
        """Return (cx, cy, radius) for the wheel."""
        s = min(self.width, self.height)
        cx = self.x + self.width / 2.0
        cy = self.y + self.height / 2.0
        return cx, cy, s / 2.0

    def _touch_to_hs(self, touch):
        """Convert a touch position to (hue, saturation)."""
        cx, cy, radius = self._get_wheel_geometry()
        dx = touch.x - cx
        dy = touch.y - cy
        dist = min(math.sqrt(dx * dx + dy * dy), radius)
        angle = math.degrees(math.atan2(dy, dx))
        hue = (angle + 360) % 360
        sat = min(100, (dist / radius) * 100)
        return hue, sat

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        cx, cy, radius = self._get_wheel_geometry()
        if math.sqrt((touch.x - cx) ** 2 + (touch.y - cy) ** 2) > radius:
            return False
        touch.grab(self)
        # Marks this as a control drag, not a navigation swipe - without it
        # PiHomeScreen.touch_up reads a horizontal drag as a page gesture and
        # slides the screen away mid-pick.
        touch.ud['ph_control_touch'] = True
        hue, sat = self._touch_to_hs(touch)
        self.dispatch("on_color_pick", hue, sat)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            hue, sat = self._touch_to_hs(touch)
            self.dispatch("on_color_pick", hue, sat)
            return True
        return False

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            hue, sat = self._touch_to_hs(touch)
            self.dispatch("on_color_pick", hue, sat)
            return True
        return False

    def on_color_pick(self, hue, saturation):
        """Default handler - parent binds via KV or Python."""
        pass
