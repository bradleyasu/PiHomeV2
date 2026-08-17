"""A single automation rule row: trigger, action, last-fired, toggle and delete.

Tapping the row body test-fires the rule; the switch enables/disables it; the
trash button deletes it. Callbacks are plain attributes assigned AFTER
construction (never as ``on_*`` constructor kwargs — Kivy would treat those as
event bindings and the callback would silently never fire; see CLAUDE.md
gotcha #11), which is why they are named ``*_cb`` rather than ``on_*``.
"""

from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty, ColorProperty, StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout

from theme.theme import Theme

Builder.load_file("./screens/Automations/automationrow.kv")

_DEFAULT_GLYPH = ""       # auto_awesome


class AutomationRow(ButtonBehavior, BoxLayout):

    rule_id     = StringProperty("")
    trigger     = StringProperty("")
    action      = StringProperty("")
    last_fired  = StringProperty("")
    glyph       = StringProperty(_DEFAULT_GLYPH)
    enabled     = BooleanProperty(True)
    can_toggle  = BooleanProperty(True)

    # Defaults derived from the active theme; the screen also passes live colors
    # at construction and rebuilds its rows when the theme changes.
    _theme = Theme()
    glyph_color  = ColorProperty(_theme.get_color(_theme.ACCENT_PRIMARY))
    text_color   = ColorProperty(_theme.get_color(_theme.TEXT_PRIMARY))
    muted_color  = ColorProperty(_theme.get_color(_theme.TEXT_SECONDARY))
    row_bg_color = ColorProperty(_theme.get_color(_theme.BACKGROUND_SURFACE))
    danger_color = ColorProperty(_theme.get_color(_theme.BUTTON_DANGER))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.select_cb = None
        self.delete_cb = None
        self._switch = None

    def attach_switch(self, switch):
        """Host the screen-built PiHomeSwitch."""
        self._switch = switch
        holder = self.ids.get("switch_holder")
        if holder is not None:
            holder.clear_widgets()
            holder.add_widget(switch)

    def on_release(self):
        # ButtonBehavior only fires this when the press was not consumed by the
        # inner delete Button or the switch, so this is the "row body" path.
        if self.select_cb:
            self.select_cb()

    def _do_delete(self):
        if self.delete_cb:
            self.delete_cb()
