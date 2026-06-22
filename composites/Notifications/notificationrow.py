import time
from datetime import datetime

from kivy.lang import Builder
from kivy.properties import (BooleanProperty, ColorProperty, StringProperty)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout

# Imported so the class registers in the Kivy Factory, making <NetworkImage>
# usable as a widget tag in notificationrow.kv (importing a Widget subclass
# auto-registers it).
from components.Image.networkimage import NetworkImage  # noqa: F401
from theme.theme import Theme

Builder.load_file("./composites/Notifications/notificationrow.kv")

# Default MaterialIcons glyph per level (used when no icon URL is provided).
_LEVEL_GLYPHS = {
    "info":    "",   # info_outline
    "warning": "",   # warning
    "error":   "",   # error
    "success": "",   # check
}
_DEFAULT_GLYPH = ""  # notifications (bell)

_LEVEL_TOKENS = {
    "info":    Theme.ALERT_INFO,
    "warning": Theme.ALERT_WARNING,
    "error":   Theme.ALERT_DANGER,
    "success": Theme.ALERT_SUCCESS,
}


def _format_ts(ts):
    """Format an epoch timestamp as a short, ASCII-only 'when issued' string.

    Relative for recent notifications ('just now', '5m ago', '3h ago',
    '2d ago'); absolute date for anything older than a week ('Jun 15').
    Computed when the row is built (rows rebuild whenever the list changes).
    """
    try:
        ts = float(ts)
    except (TypeError, ValueError):
        return ""
    delta = time.time() - ts
    if delta < 0:
        delta = 0
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    if delta < 7 * 86400:
        return f"{int(delta // 86400)}d ago"
    return datetime.fromtimestamp(ts).strftime("%b %d")


class NotificationRow(ButtonBehavior, BoxLayout):
    """A single notification row: icon, title, description, and a clear button.

    Tapping anywhere except the clear button invokes ``select_cb``; tapping the
    clear button invokes ``clear_cb``. Callbacks are assigned as plain
    attributes AFTER construction (never as on_* constructor kwargs — see
    CLAUDE.md gotcha #11).
    """

    title          = StringProperty("")
    description    = StringProperty("")
    timestamp_text = StringProperty("")
    icon_url       = StringProperty("")
    glyph          = StringProperty(_DEFAULT_GLYPH)
    has_icon       = BooleanProperty(False)

    # Defaults derived from the active theme; the parent center also passes
    # live colors at construction (and rebuilds rows on theme change).
    _theme = Theme()
    glyph_color = ColorProperty(_theme.get_color(_theme.ALERT_INFO))
    text_color  = ColorProperty(_theme.get_color(_theme.TEXT_PRIMARY))
    muted_color = ColorProperty(_theme.get_color(_theme.TEXT_SECONDARY))
    row_bg_color = ColorProperty(_theme.get_color(_theme.BACKGROUND_SURFACE))
    danger_color = ColorProperty(_theme.get_color(_theme.BUTTON_DANGER))

    def __init__(self, notification, text_color=None, muted_color=None,
                 row_bg_color=None, danger_color=None, **kwargs):
        super().__init__(**kwargs)
        self.select_cb = None
        self.clear_cb = None

        if text_color is not None:
            self.text_color = text_color
        if muted_color is not None:
            self.muted_color = muted_color
        if row_bg_color is not None:
            self.row_bg_color = row_bg_color
        if danger_color is not None:
            self.danger_color = danger_color

        self.title = notification.get("title", "") or ""
        self.description = notification.get("description", "") or ""
        self.timestamp_text = _format_ts(notification.get("ts"))

        level = notification.get("level", "info")
        theme = Theme()
        self.glyph_color = theme.get_color(_LEVEL_TOKENS.get(level, Theme.ALERT_INFO))

        icon = notification.get("icon")
        if icon:
            self.icon_url = icon
            self.has_icon = True
        else:
            self.glyph = _LEVEL_GLYPHS.get(level, _DEFAULT_GLYPH)
            self.has_icon = False

    def on_release(self):
        # ButtonBehavior only fires this when the press was NOT consumed by the
        # inner clear Button (the clear Button grabs the touch first), so this is
        # the "row body tapped" path.
        if self.select_cb:
            self.select_cb()

    def _do_clear(self):
        if self.clear_cb:
            self.clear_cb()
