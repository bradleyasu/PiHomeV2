from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import AsyncImage  
from kivy.uix.label import Label
from theme.color import Color
from theme.theme import Theme
from kivy.properties import StringProperty, BooleanProperty, NumericProperty, ColorProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp

from util.helpers import get_app
from kivy.uix.effectwidget import InvertEffect, HorizontalBlurEffect

Builder.load_file("./components/Switch/switch.kv")

class PiHomeSwitch(Widget):

    theme = Theme()
    enabled = BooleanProperty(False)
    offset = NumericProperty(0)

    track_inactive_color = theme.get_color(theme.SWITCH_INACTIVE)
    track_active_color   = theme.get_color(theme.SWITCH_ACTIVE)
    track_color  = ColorProperty(theme.get_color(theme.SWITCH_INACTIVE))
    thumb_color  = ColorProperty([1, 1, 1, 1])

    def __init__(self, size=(dp(50), dp(28)), on_change=lambda _: (), **kwargs):
        super(PiHomeSwitch, self).__init__(**kwargs)
        self.size = size
        # Called with the new value whenever the switch changes. Safe to pass as
        # a constructor kwarg (consumed here before super()) or to assign
        # afterwards; it is a plain attribute, not an on_* Kivy property.
        self.on_change = on_change
        self._suppress_change = False
        # start thumb at left inset
        self.offset = dp(3)

    def set_state(self, value, animate=True, notify=False):
        """Set the switch programmatically.

        Defaults to *not* invoking ``on_change`` — use this when reflecting
        existing state into the UI, so populating a list doesn't fire every
        row's handler (and, if that handler re-renders, loop forever).

        ``animate=False`` snaps straight to the resting position, which is what
        you want when building rows: the thumb should already be in the right
        place on the first frame rather than sliding into it. It also avoids a
        rebuilt list animating every switch at once.
        """
        value = bool(value)
        self._suppress_change = not notify
        try:
            self.enabled = value          # dispatches on_enabled only if changed
        finally:
            self._suppress_change = False
        if not animate:
            Animation.cancel_all(self, 'offset', 'track_color')
            self.offset = self._thumb_on_target() if value else dp(3)
            self.track_color = (self.track_active_color if value
                                else self.track_inactive_color)

    def _thumb_on_target(self):
        return self.width - (self.height - dp(6)) - dp(3)

    def animate_on(self):
        anim = (
            Animation(offset=self._thumb_on_target(), t='out_back', d=0.25)
            & Animation(track_color=self.track_active_color, t='out_quad', d=0.2)
        )
        anim.start(self)

    def animate_off(self):
        anim = (
            Animation(offset=dp(3), t='out_back', d=0.25)
            & Animation(track_color=self.track_inactive_color, t='out_quad', d=0.2)
        )
        anim.start(self)

    def on_enabled(self, instance, value):
        if value:
            self.animate_on()
        else:
            self.animate_off()
        # on_change was previously stored and never invoked, so the documented
        # constructor callback silently did nothing. Fire it here (suppressed
        # for programmatic set_state calls).
        if not self._suppress_change and callable(getattr(self, 'on_change', None)):
            self.on_change(value)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            # Mark this as a control interaction so the host screen doesn't also
            # read the touch as a swipe gesture (see PiHomeScreen.touch_up).
            touch.ud['ph_control_touch'] = True
            self.enabled = not self.enabled