import os
import glob
import shutil
import configparser

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty, ColorProperty, StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout

from interface.pihomescreen import PiHomeScreen
from theme.theme import Theme
from util.configuration import CONFIG
from util.const import THEME_FILE
from util.helpers import get_app, toast
from util.phlog import PIHOME_LOGGER
from util.tools import hex as hex_to_rgba

Builder.load_file("./screens/ThemeScreen/themescreen.kv")

_THEMES_DIR = "screens/ThemeScreen/themes"

# Every (section, key-base) the app resolves; each needs a _light and _dark
# variant. Used to validate that a theme is complete — an incomplete theme
# silently falls back to the built-in palette for the missing tokens.
_TOKEN_BASES = [
    ("colors", "primary"), ("colors", "secondary"),
    ("backgrounds", "primary"), ("backgrounds", "secondary"),
    ("backgrounds", "surface"), ("backgrounds", "border"),
    ("accent", "primary"),
    ("text", "primary"), ("text", "secondary"), ("text", "danger"), ("text", "success"),
    ("buttons", "primary"), ("buttons", "secondary"), ("buttons", "danger"),
    ("buttons", "success"), ("buttons", "primary_accent"), ("buttons", "secondary_accent"),
    ("switch", "active"), ("switch", "inactive"),
    ("alerts", "danger"), ("alerts", "warning"), ("alerts", "info"), ("alerts", "success"),
]
_REQUIRED_KEYS = {
    (s, f"{k}_{mode}") for s, k in _TOKEN_BASES for mode in ("light", "dark")
}

_FALLBACK = "#888888"


class ThemeCard(ButtonBehavior, BoxLayout):
    """A tappable mini-mockup preview of one theme.

    Uses ``m_*`` color property names (NOT the standard bg_color/text_color/etc.)
    on purpose: the base PiHomeScreen.on_config_update cascades to child widgets
    and overwrites the standard token props with the *active* theme. Distinct
    names keep each card showing its own palette.

    The tap callback is assigned AFTER construction (``card.select_cb = ...``),
    never as an on_* kwarg (CLAUDE.md gotcha #11).
    """

    display_name = StringProperty("")
    theme_name   = StringProperty("")
    is_active    = BooleanProperty(False)
    focused      = BooleanProperty(False)

    m_bg      = ColorProperty([0.1, 0.1, 0.1, 1])
    m_header  = ColorProperty([0.14, 0.14, 0.14, 1])
    m_surface = ColorProperty([0.18, 0.18, 0.18, 1])
    m_accent  = ColorProperty([0.5, 0.5, 0.5, 1])
    m_text    = ColorProperty([1, 1, 1, 1])
    m_muted   = ColorProperty([1, 1, 1, 0.5])
    m_alert   = ColorProperty([0.4, 0.6, 0.8, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.select_cb = None

    def on_release(self):
        if self.select_cb:
            self.select_cb()


class ThemeScreenScreen(PiHomeScreen):
    """Visual theme picker. Tapping a theme copies its ini over theme.ini and
    triggers a live reload so the whole app recolors without a restart."""

    # ── Screen chrome (auto-synced by base on_config_update) ──
    bg_color      = ColorProperty([0.10, 0.10, 0.12, 1])
    header_color  = ColorProperty([0.14, 0.14, 0.16, 1])
    surface_color = ColorProperty([1, 1, 1, 1])
    border_color  = ColorProperty([1, 1, 1, 0.1])
    text_color    = ColorProperty([1, 1, 1, 1])
    muted_color   = ColorProperty([1, 1, 1, 0.45])
    accent_color  = ColorProperty([0.74, 0.38, 0.25, 1])
    status_color  = ColorProperty([0.45, 0.45, 0.45, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cards = []
        self._focus_idx = 0
        self._apply_chrome()

    # ── Theme chrome for this screen (first paint; base handles reloads) ──

    def _apply_chrome(self):
        th = Theme()
        self.bg_color      = th.get_color(th.BACKGROUND_PRIMARY)
        self.header_color  = th.get_color(th.BACKGROUND_SECONDARY)
        self.surface_color = th.get_color(th.BACKGROUND_SURFACE)
        self.border_color  = th.get_color(th.BACKGROUND_BORDER)
        self.text_color    = th.get_color(th.TEXT_PRIMARY)
        self.muted_color   = th.get_color(th.TEXT_SECONDARY)
        self.accent_color  = th.get_color(th.ACCENT_PRIMARY)
        self.status_color  = th.get_color(th.TEXT_SECONDARY)

    # ── Lifecycle ──

    def on_enter(self, *args):
        # Rebuild each entry so previews track the current dark/light mode.
        Clock.schedule_once(lambda dt: self._build_grid(), 0)
        return super().on_enter(*args)

    # ── Theme discovery ──

    def _active_theme(self):
        return CONFIG.get("theme", "active_theme", "default")

    @staticmethod
    def _display_name(filename):
        return filename.replace("_", " ").title()

    def _load_themes(self):
        """Return a list of dicts describing each theme and its preview colors
        for the current dark/light mode."""
        dark = CONFIG.get_int("theme", "dark_mode", 0) == 1
        sfx = "dark" if dark else "light"
        themes = []
        for path in sorted(glob.glob(os.path.join(_THEMES_DIR, "*.ini"))):
            name = os.path.splitext(os.path.basename(path))[0]
            cp = configparser.ConfigParser()
            cp.optionxform = str
            try:
                cp.read(path)
            except Exception as e:
                PIHOME_LOGGER.error(f"ThemeScreen: failed to parse {name}: {e}")
                continue

            have = {(s, k) for s in cp.sections() for k in cp[s]}
            missing = _REQUIRED_KEYS - have
            if missing:
                PIHOME_LOGGER.warning(
                    f"ThemeScreen: theme '{name}' is missing {len(missing)} keys "
                    f"(will fall back to built-in colors): {sorted(missing)[:4]}..."
                )

            def col(section, key):
                try:
                    return hex_to_rgba(cp.get(section, f"{key}_{sfx}"))
                except Exception:
                    return hex_to_rgba(_FALLBACK)

            themes.append({
                "name": name,
                "display_name": self._display_name(name),
                "m_bg":      col("backgrounds", "primary"),
                "m_header":  col("backgrounds", "secondary"),
                "m_surface": col("backgrounds", "surface"),
                "m_accent":  col("accent", "primary"),
                "m_text":    col("text", "primary"),
                "m_muted":   col("text", "secondary"),
                "m_alert":   col("alerts", "info"),
            })
        return themes

    # ── Grid construction ──

    def _build_grid(self):
        grid = self.ids.get("theme_grid")
        if grid is None:
            return
        grid.clear_widgets()
        self._cards = []
        active = self._active_theme()
        for t in self._load_themes():
            card = ThemeCard(
                display_name=t["display_name"],
                theme_name=t["name"],
                m_bg=t["m_bg"], m_header=t["m_header"], m_surface=t["m_surface"],
                m_accent=t["m_accent"], m_text=t["m_text"], m_muted=t["m_muted"],
                m_alert=t["m_alert"],
                is_active=(t["name"] == active),
            )
            # Assign tap callback AFTER construction (gotcha #11).
            card.select_cb = (lambda n=t["name"]: self._apply_theme(n))
            grid.add_widget(card)
            self._cards.append(card)
        self._focus_idx = next(
            (i for i, c in enumerate(self._cards) if c.is_active), 0
        )

    # ── Apply ──

    def _apply_theme(self, name):
        src = os.path.join(_THEMES_DIR, f"{name}.ini")
        if not os.path.isfile(src):
            toast("Theme file not found", "error", 3)
            return
        try:
            shutil.copyfile(src, THEME_FILE)
            CONFIG.set("theme", "active_theme", name)
            get_app().reload_configuration()
        except Exception as e:
            PIHOME_LOGGER.error(f"ThemeScreen: failed to apply '{name}': {e}")
            toast("Failed to apply theme", "error", 3)
            return

        for c in self._cards:
            c.is_active = (c.theme_name == name)
        toast(f"Applied {self._display_name(name)}", "success", 2)

    # ── Rotary encoder ──

    def _set_focus(self, idx):
        if not self._cards:
            return
        self._focus_idx = idx % len(self._cards)
        for i, c in enumerate(self._cards):
            c.focused = (i == self._focus_idx)
        card = self._cards[self._focus_idx]
        scroll = self.ids.get("theme_scroll")
        if scroll is not None:
            scroll.scroll_to(card, padding=dp(20), animate=True)

    def on_rotary_turn(self, direction, button_pressed):
        if not self._cards:
            return True
        self._set_focus(self._focus_idx + (1 if direction > 0 else -1))
        return True

    def on_rotary_pressed(self):
        if self._cards:
            self._apply_theme(self._cards[self._focus_idx].theme_name)
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True
