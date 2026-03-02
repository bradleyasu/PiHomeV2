from kivy.lang import Builder
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, ColorProperty
from kivy.metrics import dp
from theme.theme import Theme

Builder.load_file("./components/Slider/haslider.kv")


class HASlider(Widget):
    """
    Horizontal pill slider — visually consistent with PiHomeSwitch.

    Properties
    ----------
    value       : float, 0-100
    fill_color  : RGBA — the filled/active portion (defaults to switch-active green)
    track_color : RGBA — the dim background track
    thumb_color : RGBA — the draggable thumb
    """
    theme = Theme()

    value       = NumericProperty(0.0)
    fill_color  = ColorProperty(theme.get_color(theme.SWITCH_ACTIVE))
    track_color = ColorProperty([1.0, 1.0, 1.0, 0.12])
    thumb_color = ColorProperty([1.0, 1.0, 1.0, 0.95])

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._set_from_x(touch.x)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            self._set_from_x(touch.x)
            return True
        return super().on_touch_move(touch)

    def _set_from_x(self, x):
        """Map an absolute x coordinate → value 0-100, accounting for thumb radius."""
        thumb_r = dp(11)
        usable  = max(self.width - dp(22), 1.0)
        rel     = (x - self.x - thumb_r) / usable
        self.value = max(0.0, min(100.0, rel * 100.0))
