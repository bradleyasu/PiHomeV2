from kivy.uix.widget import Widget
from kivy.properties import NumericProperty
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window


class PulseWidget(Widget):
    """Apple Intelligence-style border glow effect.

    Draws soft gradient strips along all four screen edges.  The glow
    color rotates slowly through a palette and fades in/out on burst().
    No shaders — pure canvas instructions, instant activation.
    """

    glow_opacity = NumericProperty(0.0)
    _hue_phase = NumericProperty(0.0)

    # Gradient depth from the edge inward
    EDGE_DEPTH = 45

    # Color stops for the slow hue rotation (soft pastels)
    _PALETTE = [
        [0.45, 0.55, 1.0],   # soft blue
        [0.65, 0.40, 1.0],   # lavender
        [0.90, 0.45, 0.85],  # pink
        [1.00, 0.55, 0.45],  # coral
        [0.65, 0.40, 1.0],   # lavender (wrap)
        [0.45, 0.55, 1.0],   # soft blue (wrap)
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = Window.size
        self.pos = (0, 0)

        w, h = Window.size
        d = self.EDGE_DEPTH

        # Build gradient textures — each edge gets its own so the bright
        # side always faces the screen edge.
        #
        # Horizontal textures (1 x depth):
        #   bottom: bright at row 0 (bottom of texture = screen bottom edge)
        #   top:    bright at row depth-1 (top of texture = screen top edge)
        #
        # Vertical textures (depth x 1):
        #   left:  bright at col 0 (left of texture = screen left edge)
        #   right: bright at col depth-1 (right of texture = screen right edge)

        self._tex_bottom = self._make_gradient_texture(d, axis="y", flip=False)
        self._tex_top = self._make_gradient_texture(d, axis="y", flip=True)
        self._tex_left = self._make_gradient_texture(d, axis="x", flip=False)
        self._tex_right = self._make_gradient_texture(d, axis="x", flip=True)

        with self.canvas:
            # Bottom edge
            self._c_bottom = Color(1, 1, 1, 0)
            self._r_bottom = Rectangle(
                texture=self._tex_bottom,
                pos=(0, 0),
                size=(w, d),
            )
            # Top edge
            self._c_top = Color(1, 1, 1, 0)
            self._r_top = Rectangle(
                texture=self._tex_top,
                pos=(0, h - d),
                size=(w, d),
            )
            # Left edge
            self._c_left = Color(1, 1, 1, 0)
            self._r_left = Rectangle(
                texture=self._tex_left,
                pos=(0, 0),
                size=(d, h),
            )
            # Right edge
            self._c_right = Color(1, 1, 1, 0)
            self._r_right = Rectangle(
                texture=self._tex_right,
                pos=(w - d, 0),
                size=(d, h),
            )

        self._anim = None
        self._color_event = None
        self.bind(glow_opacity=self._update_colors)
        self.bind(_hue_phase=self._update_colors)
        Window.bind(size=self._on_window_resize)

    def _make_gradient_texture(self, depth, axis="y", flip=False):
        """Create a gradient texture: opaque at the edge, transparent inward.

        axis="y" → 1 x depth texture (for top/bottom edges)
        axis="x" → depth x 1 texture (for left/right edges)
        flip=False → bright at the start (row 0 / col 0)
        flip=True  → bright at the end (row depth-1 / col depth-1)
        """
        pixels = []
        for i in range(depth):
            alpha = int(255 * (1.0 - i / depth) ** 2.0)
            pixels.append(bytes([255, 255, 255, alpha]))

        if flip:
            pixels.reverse()

        data = b"".join(pixels)

        if axis == "y":
            tex = Texture.create(size=(1, depth), colorfmt="rgba")
        else:
            tex = Texture.create(size=(depth, 1), colorfmt="rgba")

        tex.blit_buffer(data, colorfmt="rgba", bufferfmt="ubyte")
        tex.wrap = "clamp_to_edge"
        tex.mag_filter = "linear"
        return tex

    def _lerp_color(self, phase):
        """Interpolate through the palette based on phase (0..len-1)."""
        palette = self._PALETTE
        n = len(palette)
        phase = phase % (n - 1)
        idx = int(phase)
        t = phase - idx
        c0 = palette[idx]
        c1 = palette[min(idx + 1, n - 1)]
        return [c0[i] + (c1[i] - c0[i]) * t for i in range(3)]

    def _update_colors(self, *_args):
        """Apply current glow_opacity and hue_phase to all four edge colors."""
        rgb = self._lerp_color(self._hue_phase)
        a = self.glow_opacity

        # Slightly different hue offsets per edge for a flowing look
        rgb_top = self._lerp_color(self._hue_phase + 1.2)
        rgb_left = self._lerp_color(self._hue_phase + 0.6)
        rgb_right = self._lerp_color(self._hue_phase + 1.8)

        self._c_bottom.rgba = [rgb[0], rgb[1], rgb[2], a]
        self._c_top.rgba = [rgb_top[0], rgb_top[1], rgb_top[2], a]
        self._c_left.rgba = [rgb_left[0], rgb_left[1], rgb_left[2], a * 0.7]
        self._c_right.rgba = [rgb_right[0], rgb_right[1], rgb_right[2], a * 0.7]

    def _on_window_resize(self, _win, size):
        w, h = size
        d = self.EDGE_DEPTH
        self.size = (w, h)
        self.pos = (0, 0)
        self._r_bottom.pos = (0, 0)
        self._r_bottom.size = (w, d)
        self._r_top.pos = (0, h - d)
        self._r_top.size = (w, d)
        self._r_left.pos = (0, 0)
        self._r_left.size = (d, h)
        self._r_right.pos = (w - d, 0)
        self._r_right.size = (d, h)

    def burst(self):
        """Trigger the glow: fade in quickly, color-shift, fade out."""
        # Cancel ALL animations on this widget (opacity + any orphaned hue anims)
        Animation.cancel_all(self)
        if self._color_event:
            self._color_event.cancel()
            self._color_event = None

        # Ensure we're positioned correctly (parent layout may have moved us)
        w, h = Window.size
        d = self.EDGE_DEPTH
        self.pos = (0, 0)
        self.size = (w, h)
        self._r_bottom.pos = (0, 0)
        self._r_bottom.size = (w, d)
        self._r_top.pos = (0, h - d)
        self._r_top.size = (w, d)
        self._r_left.pos = (0, 0)
        self._r_left.size = (d, h)
        self._r_right.pos = (w - d, 0)
        self._r_right.size = (d, h)

        self.glow_opacity = 0.0
        self._hue_phase = 0.0

        # Fade in fast, hold briefly, fade out smooth
        fade_in = Animation(glow_opacity=0.85, t="out_cubic", d=0.15)
        hold = Animation(glow_opacity=0.75, t="linear", d=0.6)
        fade_out = Animation(glow_opacity=0.0, t="in_cubic", d=0.8)

        self._anim = fade_in + hold + fade_out

        def _on_complete(*_args):
            if self._color_event:
                self._color_event.cancel()
                self._color_event = None

        self._anim.bind(on_complete=_on_complete)
        self._anim.start(self)

        # Animate the hue rotation alongside (parallel with opacity)
        self._hue_anim = Animation(_hue_phase=4.0, t="linear", d=1.55)
        self._hue_anim.start(self)

        # Tick color updates at 30fps during the effect
        self._color_event = Clock.schedule_interval(self._update_colors, 1 / 30.0)


PULSER = PulseWidget()
