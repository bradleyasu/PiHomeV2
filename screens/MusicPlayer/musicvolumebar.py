"""
screens/MusicPlayer/musicvolumebar.py

Sleek horizontal volume slider for the Music Player screen.

Drag (or tap) anywhere on the bar to set the volume.
The caller is responsible for hooking on_value_change to drive AUDIO_PLAYER.set_volume().
"""

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, NumericProperty
from kivy.uix.widget import Widget

from theme.theme import Theme

Builder.load_file("./screens/MusicPlayer/musicvolumebar.kv")

_HANDLE_R = dp(7)   # half the handle circle diameter


class MusicVolumeBar(Widget):
    """
    Properties
    ----------
    value        : float 0.0–1.0  — current volume
    fill_w       : float (computed) — pixel width of the filled track segment
    accent_color : RGBA of the filled track & handle
    track_color  : RGBA of the dim background track
    """

    value        = NumericProperty(1.0)
    fill_w       = NumericProperty(0.0)   # kept in sync with value, used by KV canvas

    accent_color = ColorProperty([0.36, 0.67, 1.0, 1.0])
    track_color  = ColorProperty([1.0,  1.0,  1.0, 0.16])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        theme = Theme()
        self.accent_color = theme.get_color(theme.ALERT_INFO)
        # Recompute fill_w whenever value or width changes
        self.bind(value=self._sync, width=self._sync, x=self._sync)

    # ── layout sync ───────────────────────────────────────────────────────────

    def _sync(self, *_):
        """Map value [0,1] → pixel offset fill_w for the KV canvas."""
        pad    = _HANDLE_R
        usable = max(0.0, self.width - 2.0 * pad)
        self.fill_w = pad + max(0.0, min(1.0, self.value)) * usable

    # ── touch input ───────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self._set_from_x(touch.x)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self._set_from_x(touch.x)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)

    def _set_from_x(self, x):
        pad    = _HANDLE_R
        usable = max(1.0, self.width - 2.0 * pad)
        self.value = max(0.0, min(1.0, (x - self.x - pad) / usable))
