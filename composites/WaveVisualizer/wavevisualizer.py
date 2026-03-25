"""
wavevisualizer.py

Ambient wave animation inspired by the Zune desktop visualizer.
Renders 2-3 layered, translucent sine waves along the bottom of the screen
that gently pulse and drift when audio is playing on the DAC.

Audio detection is done by polling /proc/asound status (read-only, non-intrusive).
No FFT — the animation is purely procedural.
"""

import math

from kivy.clock import Clock
from kivy.graphics import Color, Mesh, InstructionGroup
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.widget import Widget

from util.phlog import PIHOME_LOGGER


# ── Wave layer definitions ───────────────────────────────────────────────────
# Each tuple: (color_rgba, base_amplitude_dp, freq_multiplier, phase_offset, speed)
WAVE_LAYERS = [
    # Deep warm layer — slow, wide
    ([0.85, 0.35, 0.20, 0.25], 28, 0.8, 0.0, 0.4),
    # Mid purple layer — medium motion
    ([0.55, 0.25, 0.75, 0.20], 22, 1.2, 2.1, 0.6),
    # Bright amber accent — faster, thinner
    ([0.95, 0.65, 0.15, 0.18], 16, 1.8, 4.2, 0.9),
]

PROC_PATH = "/proc/asound/card1/pcm0p/sub0/status"


class WaveVisualizer(Widget):
    """Ambient bottom-edge wave animation that activates when audio plays."""

    audio_playing = BooleanProperty(False)
    _target_amplitude = NumericProperty(0)
    _current_amplitude = NumericProperty(0)

    # Shared 1x2 gradient texture (opaque at bottom, transparent at top)
    _gradient_tex = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._wave_group = InstructionGroup()
        self.canvas.add(self._wave_group)
        self._time = 0.0
        self._anim_clock = None
        self._poll_clock = None

    @classmethod
    def _get_gradient_texture(cls):
        if cls._gradient_tex is None:
            tex = Texture.create(size=(1, 2), colorfmt='rgba')
            buf = bytes([
                255, 255, 255, 0,     # top: transparent
                255, 255, 255, 255,   # bottom: opaque
            ])
            tex.blit_buffer(buf, colorfmt='rgba', bufferfmt='ubyte')
            cls._gradient_tex = tex
        return cls._gradient_tex

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self):
        """Begin polling for audio and animating."""
        if self._poll_clock is None:
            self._poll_clock = Clock.schedule_interval(self._poll_audio, 2.0)
            self._poll_audio(0)  # check immediately
        if self._anim_clock is None:
            self._anim_clock = Clock.schedule_interval(self._tick, 1 / 30.0)

    def stop(self):
        """Stop all clocks and clear visuals."""
        if self._poll_clock is not None:
            self._poll_clock.cancel()
            self._poll_clock = None
        if self._anim_clock is not None:
            self._anim_clock.cancel()
            self._anim_clock = None
        self._wave_group.clear()
        self._current_amplitude = 0
        self._target_amplitude = 0
        self.audio_playing = False

    # ── Audio detection ──────────────────────────────────────────────────────

    def _poll_audio(self, dt):
        """Check if audio is actively playing on the DAC."""
        try:
            with open(PROC_PATH, 'r') as f:
                content = f.read(128)
            self.audio_playing = 'state: RUNNING' in content
        except (FileNotFoundError, PermissionError, OSError):
            self.audio_playing = False

    def on_audio_playing(self, instance, value):
        self._target_amplitude = 1.0 if value else 0.0

    # ── Animation tick ───────────────────────────────────────────────────────

    def _tick(self, dt):
        self._time += dt

        # Smooth amplitude ramp (fade in/out over ~1.5s)
        diff = self._target_amplitude - self._current_amplitude
        if abs(diff) > 0.005:
            self._current_amplitude += diff * min(1.0, dt * 2.0)
        else:
            self._current_amplitude = self._target_amplitude

        # Skip drawing if fully faded out
        if self._current_amplitude < 0.01:
            self._wave_group.clear()
            return

        self._draw_waves()

    def _draw_waves(self):
        self._wave_group.clear()

        w = self.width
        h = self.height
        x0 = self.x
        y0 = self.y

        if w <= 0 or h <= 0:
            return

        amp_scale = self._current_amplitude
        t = self._time

        # Number of horizontal segments
        segments = max(20, int(w / dp(12)))
        dx = w / segments

        tex = self._get_gradient_texture()

        for color_rgba, base_amp, freq_mult, phase, speed in WAVE_LAYERS:
            amp = dp(base_amp) * amp_scale

            # Gentle amplitude modulation (breathing)
            breath = 0.7 + 0.3 * math.sin(t * speed * 0.5 + phase)
            amp *= breath

            r, g, b, a = color_rgba
            a *= amp_scale  # fade alpha with amplitude

            self._wave_group.add(Color(r, g, b, a))

            # Build mesh vertices: pairs of (wave point, bottom point)
            vertices = []
            indices = []

            for i in range(segments + 1):
                px = x0 + i * dx
                frac = i / segments  # 0..1 across width

                # Overlaid sine waves for organic motion
                y_wave = (
                    math.sin(frac * math.pi * 2.0 * freq_mult + t * speed + phase) * 0.5
                    + math.sin(frac * math.pi * 3.5 * freq_mult + t * speed * 0.7 + phase * 1.3) * 0.25
                    + math.sin(frac * math.pi * 5.0 * freq_mult + t * speed * 1.3 + phase * 0.7) * 0.15
                )
                py_top = y0 + h * 0.15 + y_wave * amp
                py_bottom = y0

                # Each segment point contributes two vertices:
                # top (at wave) with tex v=0 (transparent)
                # bottom with tex v=1 (opaque)
                vi = len(vertices) // 4
                vertices.extend([px, py_top, frac, 0.0])     # wave crest
                vertices.extend([px, py_bottom, frac, 1.0])   # bottom edge

                if i > 0:
                    # Two triangles forming a quad between this column and the previous
                    tl = vi - 2  # prev top
                    bl = vi - 1  # prev bottom
                    tr = vi      # curr top
                    br = vi + 1  # curr bottom
                    indices.extend([tl, bl, br, tl, br, tr])

            self._wave_group.add(
                Mesh(vertices=vertices, indices=indices,
                     mode='triangles', texture=tex)
            )
