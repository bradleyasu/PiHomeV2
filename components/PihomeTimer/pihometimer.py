import time

from kivy.clock import Clock
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

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        Clock.schedule_interval(self.update, 1 / 10)
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