import time

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from components.Msgbox.msgbox import MSGBOX_FACTORY
from services.timers.timer import Timer

Builder.load_file("./components/PihomeTimer/pihometimer.kv")

# Cool-blue accent, shifts to amber / red as time runs out
_ACCENT_NORMAL = [0.39, 0.71, 1.00, 1.0]
_ACCENT_WARN   = [1.00, 0.60, 0.20, 1.0]   # < 60 s
_ACCENT_URGENT = [1.00, 0.28, 0.28, 1.0]   # < 15 s


class PiHomeTimer(BoxLayout):
    """Single-timer row widget used inside TimerDrawer's expandable tray."""

    label        = StringProperty("Timer")
    time_label   = StringProperty("--:--:--")
    progress     = NumericProperty(1.0)          # 1.0 = full → 0.0 = expired

    bg_color     = ColorProperty([0.11, 0.13, 0.19, 1.00])
    accent_color = ColorProperty(_ACCENT_NORMAL)
    text_color   = ColorProperty([1.0, 1.0, 1.0, 0.90])
    muted_color  = ColorProperty([1.0, 1.0, 1.0, 0.40])

    def __init__(self, timer=None, **kwargs):
        super().__init__(**kwargs)
        self.timer = timer or Timer(60)
        self.label = self.timer.label
        Clock.schedule_once(self._build_canvas)

    # ── canvas (all imperative — no KV canvas blocks) ─────────────────────────

    def _build_canvas(self, *args):
        # ── root background ──────────────────────────────────────────────────
        with self.canvas.before:
            self._bg_color_inst = Color(*self.bg_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg,
                  bg_color=lambda *a: setattr(self._bg_color_inst, 'rgba', self.bg_color))

        # ── arc widget (Ellipse-only, no Line — avoids Pi GL corruption) ──────────
        arc = self.ids.arc_widget
        hole = dp(10)
        with arc.canvas:
            # Full track ring background
            self._track_color = Color(*self.muted_color)
            self._track_ellipse = Ellipse(pos=arc.pos, size=arc.size,
                                          angle_start=0, angle_end=360)
            # Progress pie sector (filled wedge, masked by center hole)
            self._prog_color = Color(*self.accent_color)
            self._prog_ellipse = Ellipse(pos=arc.pos, size=arc.size,
                                         angle_start=90, angle_end=90)
            # Center hole to turn pie into a ring
            self._hole_color = Color(*self.bg_color)
            self._hole_ellipse = Ellipse(
                pos=(arc.x + hole / 2, arc.y + hole / 2),
                size=(arc.width - hole, arc.height - hole),
            )
        self._update_arc()
        arc.bind(pos=lambda *a: self._update_arc(),
                 size=lambda *a: self._update_arc())
        self.bind(progress=lambda *a: self._update_arc(),
                  accent_color=lambda *a: self._update_arc(),
                  muted_color=lambda *a: self._update_arc(),
                  bg_color=lambda *a: self._update_arc())

        # ── cancel label pill background ─────────────────────────────────────
        cancel = self.ids.cancel_lbl
        with cancel.canvas.before:
            self._cancel_bg = Color(1, 1, 1, 0.08)
            self._cancel_ellipse = Ellipse(pos=cancel.pos, size=cancel.size)
        cancel.bind(pos=self._update_cancel, size=self._update_cancel)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _update_arc(self, *args):
        arc = self.ids.arc_widget
        hole = dp(10)
        self._track_color.rgba = self.muted_color
        self._track_ellipse.pos = arc.pos
        self._track_ellipse.size = arc.size

        self._prog_color.rgba = self.accent_color
        self._prog_ellipse.pos = arc.pos
        self._prog_ellipse.size = arc.size
        # Clockwise sweep from 12-o'clock (90°)
        self._prog_ellipse.angle_start = 90 - 360 * self.progress
        self._prog_ellipse.angle_end = 90

        self._hole_color.rgba = self.bg_color
        self._hole_ellipse.pos = (arc.x + hole / 2, arc.y + hole / 2)
        self._hole_ellipse.size = (arc.width - hole, arc.height - hole)


    def _update_cancel(self, *args):
        cancel = self.ids.cancel_lbl
        self._cancel_ellipse.pos = cancel.pos
        self._cancel_ellipse.size = cancel.size

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        Clock.schedule_interval(self.update, 1.0)  # 1 Hz — HH:MM:SS only needs per-second precision
        self.timer.add_listener(self.destroy)
        self.timer.start()

    def update(self, dt):
        t = self.timer
        if not t or not t.is_running:
            return
        elapsed   = t.get_elapsed_time()
        time_left = max(0.0, t.duration - elapsed)

        self.progress   = time_left / t.duration if t.duration > 0 else 0.0
        self.time_label = time.strftime("%H:%M:%S", time.gmtime(time_left))

        if time_left < 15:
            self.accent_color = _ACCENT_URGENT
        elif time_left < 60:
            self.accent_color = _ACCENT_WARN
        else:
            self.accent_color = _ACCENT_NORMAL

    def destroy(self, time_left):
        Clock.unschedule(self.update)
        self.timer = None

    # ── cancel interaction ────────────────────────────────────────────────────

    def _do_cancel(self):
        if self.timer:
            MSGBOX_FACTORY.show(
                "Cancel Timer",
                f"Remove '{self.label}'?",
                0, 0, 1,
                self._confirm_cancel,
            )

    def _confirm_cancel(self):
        if self.timer:
            self.timer.cancel()

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if 'cancel_lbl' in self.ids:
            lbl = self.ids.cancel_lbl
            if lbl.collide_point(*touch.pos):
                self._do_cancel()
                return True
        return False