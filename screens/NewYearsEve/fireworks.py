from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse
from kivy.clock import Clock
from random import randint, choice

from screens.NewYearsEve.firework import FireworkBurst

COLOR_PALETTES = [
    [(1.0, 0.85, 0.2), (1.0, 0.6, 0.1)],           # gold/amber
    [(1.0, 0.2, 0.15), (1.0, 0.5, 0.2)],             # red/orange
    [(0.2, 0.4, 1.0), (0.3, 0.8, 1.0)],              # blue/cyan
    [(0.1, 0.9, 0.4), (0.2, 1.0, 0.7)],              # green/teal
    [(0.7, 0.2, 1.0), (1.0, 0.3, 0.7)],              # purple/magenta
    [(1.0, 1.0, 1.0), (0.8, 0.85, 0.9)],             # white/silver
]

INTENSITY_CONFIG = {
    "ambient":     {"spawn_interval": 2.0, "particle_count": 15},
    "building":    {"spawn_interval": 1.0, "particle_count": 20},
    "climax":      {"spawn_interval": 0.3, "particle_count": 25},
    "celebration": {"spawn_interval": 0.15, "particle_count": 30},
}

MAX_BURSTS = 8


class Fireworks(Widget):

    def __init__(self, **kwargs):
        super(Fireworks, self).__init__(**kwargs)
        self.bursts = []
        self.intensity = "ambient"
        self._update_event = None
        self._spawn_event = None
        self._celebration_timeout = None

    def set_intensity(self, level):
        if level not in INTENSITY_CONFIG:
            return
        if level == self.intensity:
            return
        self.intensity = level
        # Reschedule spawn rate for new intensity
        if self._spawn_event:
            self._spawn_event.cancel()
        interval = INTENSITY_CONFIG[level]["spawn_interval"]
        self._spawn_event = Clock.schedule_interval(self._spawn_burst, interval)
        # Auto-dial-back celebration after 120s
        if self._celebration_timeout:
            self._celebration_timeout.cancel()
            self._celebration_timeout = None
        if level == "celebration":
            self._celebration_timeout = Clock.schedule_once(
                lambda dt: self.set_intensity("ambient"), 120
            )

    def _spawn_burst(self, dt):
        if len(self.bursts) >= MAX_BURSTS:
            return
        w = self.width if self.width > 0 else 800
        h = self.height if self.height > 0 else 480
        cx = randint(int(w * 0.1), int(w * 0.9))
        cy = randint(int(h * 0.3), int(h * 0.9))
        palette = choice(COLOR_PALETTES)
        count = INTENSITY_CONFIG[self.intensity]["particle_count"]
        burst = FireworkBurst(cx, cy, palette, count)
        self.bursts.append(burst)

    def _update(self, dt):
        # Tick all bursts
        for burst in self.bursts:
            burst.tick(dt)
        # Remove dead bursts
        self.bursts = [b for b in self.bursts if not b.is_dead()]
        # Batch redraw
        self.canvas.clear()
        for burst in self.bursts:
            for x, y, size, r, g, b, opacity in burst.get_draw_data():
                with self.canvas:
                    Color(r, g, b, opacity)
                    Ellipse(pos=(x - size / 2, y - size / 2), size=(size, size))

    def start_fireworks(self):
        interval = INTENSITY_CONFIG[self.intensity]["spawn_interval"]
        self._spawn_event = Clock.schedule_interval(self._spawn_burst, interval)
        self._update_event = Clock.schedule_interval(self._update, 1 / 30)

    def stop_fireworks(self):
        if self._spawn_event:
            self._spawn_event.cancel()
            self._spawn_event = None
        if self._update_event:
            self._update_event.cancel()
            self._update_event = None
        if self._celebration_timeout:
            self._celebration_timeout.cancel()
            self._celebration_timeout = None
        self.canvas.clear()
        self.bursts = []
