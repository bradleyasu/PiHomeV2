"""HSV color wheel widget for PiHome Nanoleaf screen.

Renders a circular HSV wheel as a pre-generated texture.  Touch to pick
hue (angle) and saturation (distance from centre).  A separate brightness
value is exposed as a property so the parent can bind a slider to it.

Touch interaction dispatches ``on_color_pick(hue, saturation)`` so the
parent can update its own state without fighting KV expression bindings.
"""

import colorsys
import math

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse
from kivy.graphics.texture import Texture
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.widget import Widget

_TEX_SIZE = 256  # wheel texture resolution (NxN)


class ColorWheel(Widget):
    """Circular HSV colour picker.

    Properties ``hue``, ``saturation``, ``brightness`` can be set from
    outside (e.g. KV bindings) to display the current state.  When the
    user *touches* the wheel, ``on_color_pick`` is dispatched with the
    new (hue, saturation) values — the parent should handle that event
    and update its own properties which will flow back via KV bindings.
    """

    hue = NumericProperty(0)            # 0-360 degrees
    saturation = NumericProperty(100)   # 0-100
    brightness = NumericProperty(100)   # 0-100  (V in HSV)
    selected_color = ListProperty([255, 0, 0])  # RGB 0-255 (includes brightness)

    __events__ = ("on_color_pick",)

    _wheel_tex = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._generate_texture()
        self.bind(size=self._redraw, pos=self._redraw,
                  hue=self._on_hsv_change, saturation=self._on_hsv_change,
                  brightness=self._on_hsv_change)
        Clock.schedule_once(lambda dt: self._redraw(), 0)

    # ── Texture generation (once) ─────────────────────────────────────────────

    def _generate_texture(self):
        size = _TEX_SIZE
        buf = bytearray(size * size * 4)
        center = size / 2.0
        radius = size / 2.0

        for y in range(size):
            for x in range(size):
                dx = x - center
                dy = y - center
                dist = math.sqrt(dx * dx + dy * dy)
                idx = (y * size + x) * 4

                if dist <= radius:
                    angle = math.atan2(dy, dx)
                    h = (math.degrees(angle) + 360) % 360 / 360.0
                    s = dist / radius
                    r, g, b = colorsys.hsv_to_rgb(h, s, 1.0)
                    buf[idx]     = int(r * 255)
                    buf[idx + 1] = int(g * 255)
                    buf[idx + 2] = int(b * 255)
                    buf[idx + 3] = 255
                else:
                    buf[idx] = buf[idx + 1] = buf[idx + 2] = buf[idx + 3] = 0

        tex = Texture.create(size=(size, size), colorfmt="rgba")
        tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
        tex.flip_vertical()
        self._wheel_tex = tex

    # ── Drawing ───────────────────────────────────────────────────────────────

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

    # ── Colour computation ────────────────────────────────────────────────────

    def _on_hsv_change(self, *args):
        h = self.hue / 360.0
        s = self.saturation / 100.0
        v = self.brightness / 100.0
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        self.selected_color = [int(r * 255), int(g * 255), int(b * 255)]
        self._redraw()

    # ── Touch handling ────────────────────────────────────────────────────────

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
        """Default handler — parent binds via KV or Python."""
        pass
