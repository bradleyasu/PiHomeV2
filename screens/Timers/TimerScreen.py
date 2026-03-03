"""
screens/Timers/TimerScreen.py

Redesigned timer creation screen.

Features:
  • Quick-start chips  — tap to fire a preset timer instantly.
  • Digit controls     — HH / MM / SS spinners for precise durations.
  • Name field         — optional label for the new timer.
  • Rotary encoder     — turn to adjust the focused segment, press to start,
                         long-press to cycle focus between H → M → S.
"""

import time as _time

from kivy.clock import Clock
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from interface.pihomescreen import PiHomeScreen
from screens.Timers.timerdigitcontrol import TimerDigitControl  # noqa — registers kv rule
from theme.theme import Theme

Builder.load_file("./screens/Timers/TimerScreen.kv")

# ── Quick-start presets ───────────────────────────────────────────────────────
_QUICK_PRESETS = [
    (60,   "1 min"),
    (180,  "3 min"),
    (300,  "5 min"),
    (600,  "10 min"),
    (900,  "15 min"),
    (1800, "30 min"),
    (3600, "1 hr"),
]

# Rotary focus segments
_SEG_HOURS   = 0
_SEG_MINUTES = 1
_SEG_SECONDS = 2


class TimerScreen(PiHomeScreen):
    """
    Timer creation screen — sleek dark design with quick-start chips and
    a three-segment digit spinner for custom durations.
    """

    # ── theme colours ──────────────────────────────────────────────────────────
    bg_color     = ColorProperty([0, 0, 0, 1])
    header_color = ColorProperty([0, 0, 0, 1])
    card_color   = ColorProperty([0, 0, 0, 0.4])
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([0.5, 0.5, 0.5, 1])
    accent_color = ColorProperty([0.36, 0.67, 1.0, 1.0])

    # ── state ──────────────────────────────────────────────────────────────────
    total_seconds   = NumericProperty(0)
    focused_segment = NumericProperty(_SEG_MINUTES)  # which segment rotary controls
    focused_label   = StringProperty("MIN")          # displayed in the rotary hint pill

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        theme = Theme()
        self.bg_color     = theme.get_color(theme.BACKGROUND_PRIMARY)
        self.header_color = theme.get_color(theme.BACKGROUND_SECONDARY)
        self.text_color   = theme.get_color(theme.TEXT_PRIMARY)
        self.muted_color  = theme.get_color(theme.TEXT_SECONDARY)
        self.accent_color = theme.get_color(theme.ALERT_INFO)
        hc = self.header_color
        self.card_color = (hc[0], hc[1], hc[2], 0.90)

    # ── screen lifecycle ──────────────────────────────────────────────────────

    def on_enter(self, *args):
        super().on_enter(*args)
        self._reset()
        Clock.schedule_once(lambda _: self._build_quick_chips(), 0)
        # Keep total_seconds in sync with spinner values
        self.ids.hours_ctrl.bind(value=self._sync_total)
        self.ids.minutes_ctrl.bind(value=self._sync_total)
        self.ids.seconds_ctrl.bind(value=self._sync_total)

    def on_leave(self, *args):
        super().on_leave(*args)
        try:
            self.ids.hours_ctrl.unbind(value=self._sync_total)
            self.ids.minutes_ctrl.unbind(value=self._sync_total)
            self.ids.seconds_ctrl.unbind(value=self._sync_total)
        except Exception:
            pass

    # ── rotary encoder ────────────────────────────────────────────────────────

    def on_rotary_turn(self, direction, button_pressed):
        """Spin the currently focused digit segment."""
        ctrl = self._focused_ctrl()
        if ctrl is not None:
            ctrl.adjust(direction)
        return None

    def on_rotary_pressed(self):
        """Start the timer (if any seconds set) and return to the previous screen."""
        if self.total_seconds > 0:
            self.start_timer()
        else:
            self.go_back()
        return None

    def on_rotary_long_pressed(self):
        """Cycle rotary focus: hours → minutes → seconds → hours."""
        self.focused_segment = (int(self.focused_segment) + 1) % 3
        return None  # intentionally do NOT call super (which would stop the music player)

    def on_focused_segment(self, instance, value):
        """Keep the focused_label string in sync with the active segment."""
        self.focused_label = ["HRS", "MIN", "SEC"][int(value)]

    # ── public actions ────────────────────────────────────────────────────────

    def set_focus(self, segment: int):
        """Called from KV when the user taps a digit control card."""
        self.focused_segment = segment

    def start_timer(self):
        """Read the spinners + name field, create the timer, then go back."""
        if self.total_seconds <= 0:
            return
        name_input = self.ids.get("timer_name_input")
        name = name_input.text.strip() if name_input else ""
        if not name:
            name = self._auto_label()
        TIMER_DRAWER.create_timer(self.total_seconds, name)
        self._reset()
        # Defer navigation to the next frame so any in-flight touch/event
        # dispatch on the Pi's real touchscreen fully completes first.  Calling
        # go_back() synchronously inside a touch callback can leave the
        # NoTransition screen opacity at 0 on slower hardware.
        Clock.schedule_once(lambda _: self.go_back(), 0)

    def _touch_start_timer(self, touch):
        """Touch-safe wrapper: grab the touch then start the timer (called from KV)."""
        touch.grab(self)
        self.start_timer()

    # ── private helpers ───────────────────────────────────────────────────────

    def _reset(self):
        try:
            self.ids.hours_ctrl.reset()
            self.ids.minutes_ctrl.reset()
            self.ids.seconds_ctrl.reset()
            ni = self.ids.get("timer_name_input")
            if ni:
                ni.text = ""
        except Exception:
            pass
        self.total_seconds   = 0
        self.focused_segment = _SEG_MINUTES

    def _sync_total(self, *_):
        try:
            h = int(self.ids.hours_ctrl.value)
            m = int(self.ids.minutes_ctrl.value)
            s = int(self.ids.seconds_ctrl.value)
            self.total_seconds = h * 3600 + m * 60 + s
        except Exception:
            self.total_seconds = 0

    def _focused_ctrl(self):
        try:
            return [
                self.ids.hours_ctrl,
                self.ids.minutes_ctrl,
                self.ids.seconds_ctrl,
            ][int(self.focused_segment)]
        except Exception:
            return None

    def _auto_label(self) -> str:
        return _time.strftime("%H:%M:%S", _time.gmtime(self.total_seconds)) + " timer"

    # ── quick-start chips ─────────────────────────────────────────────────────

    def _build_quick_chips(self):
        row = self.ids.get("quick_timer_row")
        if row is None:
            return
        row.clear_widgets()
        for duration, label in _QUICK_PRESETS:
            row.add_widget(self._make_chip(duration, label))

    def _make_chip(self, duration: int, label: str) -> BoxLayout:
        """Return a pill-shaped quick-start button widget."""
        ac = list(self.accent_color)

        chip = BoxLayout(
            size_hint_x=1,
            padding=[dp(2), dp(2), dp(2), dp(2)],
        )

        with chip.canvas.before:
            _fill_c  = Color(ac[0], ac[1], ac[2], 0.12)
            _fill_rr = RoundedRectangle(pos=chip.pos, size=chip.size, radius=[dp(18)])
            _bord_c  = Color(ac[0], ac[1], ac[2], 0.30)
            _bord_l  = Line(
                rounded_rectangle=[
                    chip.x + dp(0.5), chip.y + dp(0.5),
                    chip.width - dp(1), chip.height - dp(1),
                    dp(18),
                ],
                width=dp(1),
            )

        def _sync(w, _):
            _fill_rr.pos  = w.pos
            _fill_rr.size = w.size
            _bord_l.rounded_rectangle = [
                w.x + dp(0.5), w.y + dp(0.5),
                w.width - dp(1), w.height - dp(1),
                dp(18),
            ]

        chip.bind(pos=_sync, size=_sync)

        chip_lbl = Label(
            text=label,
            font_name="Nunito",
            font_size="12sp",
            bold=True,
            color=list(ac),
            halign="center",
            valign="middle",
        )
        chip_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        chip.add_widget(chip_lbl)

        # Bind touch — start immediately and return.
        # Use touch.grab() so the Pi's touchscreen event is fully consumed
        # and does not continue propagating up the widget tree after navigation.
        def _on_touch_down(w, touch):
            if w.collide_point(*touch.pos):
                touch.grab(w)
                self._start_quick_timer(duration, label)
                return True
            return False

        def _on_touch_up(w, touch):
            if touch.grab_current is w:
                touch.ungrab(w)
                return True
            return False

        chip.bind(on_touch_down=_on_touch_down)
        chip.bind(on_touch_up=_on_touch_up)
        return chip

    def _start_quick_timer(self, duration: int, label: str):
        TIMER_DRAWER.create_timer(duration, label)
        Clock.schedule_once(lambda _: self.go_back(), 0)