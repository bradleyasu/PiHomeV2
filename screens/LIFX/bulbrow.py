"""Row and card widgets for the LIFX screen.

Each class defines ``_apply_theme()`` so ``PiHomeScreen.on_config_update``
re-themes it for free when it cascades to descendants.

Tap callbacks are plain attributes (``select_cb``, ``toggle_cb``) assigned
*after* construction, never as constructor kwargs - Kivy treats any ``on_*``
kwarg as an event binding, so a callback passed that way silently never fires.
"""

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ColorProperty,
    ListProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from theme.theme import Theme

Builder.load_file("./screens/LIFX/bulbrow.kv")

_th = Theme()

# Escape form, not pasted glyphs: an editor can silently write a raw
# glyph as an empty string and the icon then just never appears.
ICON_BULB_ON = "\ue0f0" # highlight
ICON_BULB_OFF = "\ue332" # lightbulb_outline
ICON_OFFLINE = "\ue1da" # signal_wifi_off
ICON_DELETE = "\ue872" # delete
ICON_PALETTE = "\ue40a" # palette
ICON_SUN = "\ue430"  # wb_sunny
ICON_STYLE = "\ue42a" # style
ICON_BRIGHTNESS = "\ue518" # brightness_medium
ICON_REFRESH = "\ue5d5" # refresh
ICON_SAVE = "\ue161" # save


class _Themed(object):
    """Shared theme refresh for every widget in this module."""

    def _apply_theme(self, *args):
        theme = Theme()
        self.text_color = theme.get_color(theme.TEXT_PRIMARY)
        self.muted_color = theme.get_color(theme.TEXT_SECONDARY)
        self.accent_color = theme.get_color(theme.ACCENT_PRIMARY)
        surface = theme.get_color(theme.BACKGROUND_SURFACE)
        self.row_bg_color = list(surface[:3]) + [0.70]
        self.card_color = list(surface[:3]) + [1.0]


class IconButton(ButtonBehavior, Label):
    """A tappable MaterialIcons glyph.

    Fires on *release* with visual feedback, unlike the older
    ``on_touch_down`` + ``collide_point`` idiom which also steals scroll taps.
    """

    action = None

    def on_release(self):
        if callable(self.action):
            self.action()


class SwatchButton(ButtonBehavior, Widget):
    """A flat colour chip in the preset grid."""

    swatch_color = ColorProperty([1, 1, 1, 1])
    action = None

    def on_release(self):
        if callable(self.action):
            self.action()


class ModeTab(ButtonBehavior, BoxLayout, _Themed):
    """One of COLOR / WHITE / SCENES."""

    icon = StringProperty("")
    label = StringProperty("")
    active = BooleanProperty(False)

    text_color = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    accent_color = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))
    row_bg_color = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    card_color = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))

    select_cb = None

    def on_release(self):
        if callable(self.select_cb):
            self.select_cb()


class _SwitchHost(BoxLayout, _Themed):
    """Base for rows that host a screen-built PiHomeSwitch."""

    selected = BooleanProperty(False)

    text_color = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    accent_color = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))
    row_bg_color = ColorProperty(list(_th.get_color(_th.BACKGROUND_SURFACE)[:3]) + [0.70])
    card_color = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))

    select_cb = None

    def attach_switch(self, switch):
        holder = self.ids.get("switch_holder")
        if holder is None:
            return
        holder.clear_widgets()
        holder.add_widget(switch)
        self.switch = switch


class RoomHeaderRow(ButtonBehavior, _SwitchHost):
    """A room name with its light count and a master switch."""

    room = StringProperty("")
    room_display = StringProperty("")
    subtitle = StringProperty("")

    def on_room(self, _instance, value):
        # Uppercased here, not in KV: `root.room.upper()` binds to the whole
        # attribute chain, finds `.upper` is not a property, and silently never
        # updates - the label just stays blank.
        self.room_display = (value or "").upper()

    def on_release(self):
        if callable(self.select_cb):
            self.select_cb()


class BulbRow(ButtonBehavior, _SwitchHost):
    """One bulb: colour dot, name, level, switch."""

    serial = StringProperty("")
    label = StringProperty("")
    level = StringProperty("")
    is_on = BooleanProperty(False)
    online = BooleanProperty(True)
    dot_color = ColorProperty([1, 1, 1, 1])

    def on_release(self):
        if callable(self.select_cb):
            self.select_cb()


class SceneCard(ButtonBehavior, BoxLayout, _Themed):
    """A saved scene: name, source chip, a strip of its colours, delete."""

    scene_id = StringProperty("")
    label = StringProperty("")
    source = StringProperty("local")
    swatches = ListProperty([])

    text_color = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    accent_color = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))
    row_bg_color = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    card_color = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))

    select_cb = None
    delete_cb = None

    def on_release(self):
        if callable(self.select_cb):
            self.select_cb()

    def do_delete(self):
        if callable(self.delete_cb):
            self.delete_cb()

    def on_swatches(self, _instance, value):
        strip = self.ids.get("swatch_strip")
        if strip is None:
            return
        strip.clear_widgets()
        for rgb in value[:4]:
            chip = Widget(size_hint=(None, 1), width=dp(10))
            _paint(chip, [c / 255.0 for c in rgb] + [1.0])
            strip.add_widget(chip)


class KelvinChip(ButtonBehavior, BoxLayout, _Themed):
    """A named colour-temperature preset."""

    label = StringProperty("")
    kelvin = NumericProperty(2700)
    active = BooleanProperty(False)

    text_color = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    accent_color = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))
    row_bg_color = ColorProperty(list(_th.get_color(_th.BACKGROUND_SURFACE)[:3]) + [0.70])
    card_color = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))

    select_cb = None

    def on_release(self):
        if callable(self.select_cb):
            self.select_cb()


def _paint(widget, rgba, radius=dp(3)):
    """Give a bare Widget a rounded background that tracks its geometry."""
    from kivy.graphics import Color, RoundedRectangle

    with widget.canvas.before:
        Color(*rgba)
        rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
    widget.bind(pos=lambda i, v, r=rect: setattr(r, "pos", i.pos),
                size=lambda i, v, r=rect: setattr(r, "size", i.size))
    return rect
