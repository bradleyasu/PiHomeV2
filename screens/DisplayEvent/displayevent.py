from kivy.lang import Builder
from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from services.audio.sfx import SFX
from util.const import _HOME_SCREEN
from util.tools import hex
from kivy.clock import Clock
from kivy.properties import BooleanProperty, ColorProperty, StringProperty, NumericProperty
import theme.theme as t

Builder.load_file("./screens/DisplayEvent/displayevent.kv")

class DisplayEvent(PiHomeScreen):
    """
    Informational display screen launched by external display events.
    Shows a floating card with optional image pane and auto-dismiss countdown.
    """
    background      = ColorProperty((0, 0, 0, 0.92))
    title           = StringProperty("")
    message         = StringProperty("")
    image           = StringProperty("")          # URL for the card image pane

    # ── Theme colours (auto-refreshed by PiHomeScreen.on_config_update) ────────
    card_color      = ColorProperty([1, 1, 1, 1])
    text_color      = ColorProperty([0.08, 0.08, 0.08, 1])
    muted_color     = ColorProperty([0.45, 0.45, 0.45, 1])

    # ── Image orientation (detected when texture loads) ────────────────────────
    _img_landscape  = BooleanProperty(False)

    # ── Timeout state ─────────────────────────────────────────────────────────
    timeout_seconds = NumericProperty(0)
    _target_screen  = StringProperty("")
    _remaining      = NumericProperty(0)
    _arc_angle      = NumericProperty(360)
    _tick_event     = None

    def __init__(self, **kwargs):
        super(DisplayEvent, self).__init__(**kwargs)
        theme = t.Theme()
        self.card_color  = theme.get_color(t.Theme.BACKGROUND_PRIMARY)
        self.text_color  = theme.get_color(t.Theme.TEXT_PRIMARY)
        self.muted_color = theme.get_color(t.Theme.TEXT_SECONDARY)

    # ── Public API called by the DisplayEvent event before goto() ─────────────

    def set_background(self, background):
        self.background = hex(background, 1)

    def set_timeout(self, seconds, screen=None):
        """Store timeout config. Countdown starts in on_enter once the screen
        is actually visible. seconds=0 or None means stay open indefinitely."""
        try:
            self.timeout_seconds = max(0, int(seconds))
        except (TypeError, ValueError):
            self.timeout_seconds = 0
        self._target_screen = screen or _HOME_SCREEN

    # ── Image orientation detection ────────────────────────────────────────────

    def on_image(self, instance, value):
        """Reset orientation flag whenever the image URL changes."""
        self._img_landscape = False

    def _on_img_texture(self, widget, texture):
        """Called when the AsyncImage finishes loading — detect orientation."""
        if texture is None:
            return
        self._img_landscape = texture.width >= texture.height

    # ── Countdown machinery ────────────────────────────────────────────────────

    def _start_countdown(self):
        self._stop_countdown()
        if self.timeout_seconds <= 0:
            return
        self._remaining  = self.timeout_seconds
        self._arc_angle  = 360
        self._tick_event = Clock.schedule_interval(self._tick, 1)

    def _stop_countdown(self):
        if self._tick_event:
            self._tick_event.cancel()
            self._tick_event = None

    def _tick(self, dt):
        self._remaining -= 1
        if self.timeout_seconds > 0:
            self._arc_angle = max(0, 360 * self._remaining / self.timeout_seconds)
        if self._remaining <= 0:
            self._stop_countdown()
            PIHOME_SCREEN_MANAGER.goto(self._target_screen or _HOME_SCREEN)

    # ── Screen lifecycle ───────────────────────────────────────────────────────

    def on_enter(self, *args):
        SFX.play("multi_pop")
        self._start_countdown()
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        self._stop_countdown()
        return super().on_pre_leave(*args)

    def on_touch_down(self, touch):
        self._stop_countdown()
        self.go_back()
        return super().on_touch_down(touch)
