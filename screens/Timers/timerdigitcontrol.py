"""
screens/Timers/timerdigitcontrol.py

A sleek, self-contained digit-spinner widget used by TimerScreen.
Represents a single time segment (hours, minutes, or seconds) with
up/down buttons and a large numeric display.
"""

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout

from theme.theme import Theme

Builder.load_file("./screens/Timers/timerdigitcontrol.kv")


class TimerDigitControl(BoxLayout):
    """
    Vertical three-section control:
        ▲  (up button)
       value  (large Nunito label, 2-digit zero-padded)
       unit   (small muted label, e.g. "HRS")
        ▼  (down button)

    Set `focused = True` to highlight the control in the accent colour so the
    user can see which segment the rotary encoder is acting on.
    """

    # ── value & constraints ──────────────────────────────────────────────────
    value     = NumericProperty(0)
    unit_label = StringProperty("MIN")
    min_value = NumericProperty(0)
    max_value = NumericProperty(59)
    focused   = BooleanProperty(False)

    # ── palette ───────────────────────────────────────────────────────────────
    text_color   = ColorProperty([1.0, 1.0, 1.0, 1.0])
    accent_color = ColorProperty([0.36, 0.67, 1.0, 1.0])
    muted_color  = ColorProperty([1.0, 1.0, 1.0, 0.40])
    card_color   = ColorProperty([0.12, 0.14, 0.20, 1.0])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        theme = Theme()
        self.text_color   = theme.get_color(theme.TEXT_PRIMARY)
        self.accent_color = theme.get_color(theme.ALERT_INFO)
        sc = theme.get_color(theme.BACKGROUND_SECONDARY)
        # Slightly lighter card surface so it stands out from the page bg
        self.card_color = (
            min(sc[0] * 1.25, 1.0),
            min(sc[1] * 1.25, 1.0),
            min(sc[2] * 1.25, 1.0),
            1.0,
        )
        muted = list(theme.get_color(theme.TEXT_SECONDARY))
        muted[3] = 0.45
        self.muted_color = muted

    # ── public API ────────────────────────────────────────────────────────────

    def increment(self):
        """Wrap-around increment."""
        self.value = (int(self.value) + 1) % (self.max_value + 1)

    def decrement(self):
        """Wrap-around decrement."""
        self.value = (int(self.value) - 1) % (self.max_value + 1)

    def adjust(self, delta: int):
        """Clamp-adjusted change — used by the rotary encoder."""
        new_val = int(self.value) + delta
        self.value = max(self.min_value, min(self.max_value, new_val))

    def reset(self):
        self.value = 0

    def _touch_increment(self, touch):
        """Increment and consume the touch (called from KV)."""
        touch.grab(self)
        self.increment()

    def _touch_decrement(self, touch):
        """Decrement and consume the touch (called from KV)."""
        touch.grab(self)
        self.decrement()
