"""
Home Assistant device cards.

HADeviceCard      — base class (shared fields + API call helper)
  HALightCard     — light.* : on/off switch + brightness slider
  HAToggleCard    — switch.* | input_boolean.* | fan.*  : on/off switch
  HACoverCard     — cover.*  : open / close buttons
  HATriggerCard   — scene.* | script.* : single "Run" button

make_ha_card(entity_id, state_dict) → correct subclass instance | None
"""
import json
import os
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (BooleanProperty, ColorProperty,
                              NumericProperty, StringProperty)
from kivy.uix.boxlayout import BoxLayout

from components.Slider.haslider import HASlider          # noqa — registers rule
from components.Switch.switch import PiHomeSwitch        # noqa — registers rule
from services.homeassistant.homeassistant import HOME_ASSISTANT
from theme.theme import Theme
from util.phlog import PIHOME_LOGGER

Builder.load_file("./composites/HomeAssistant/hadevicecard.kv")

# ── Favorites persistence ─────────────────────────────────────────────────────
_FAVORITES_FILE = "./cache/ha_favorites.json"


def load_ha_favorites() -> set:
    """Return the set of favorited entity_ids from disk."""
    try:
        with open(_FAVORITES_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_ha_favorites(favs: set):
    """Persist the favorites set to disk."""
    os.makedirs(os.path.dirname(_FAVORITES_FILE), exist_ok=True)
    try:
        with open(_FAVORITES_FILE, "w") as f:
            json.dump(sorted(favs), f)
    except Exception as e:
        PIHOME_LOGGER.error(f"Could not save HA favorites: {e}")


# ── Domain → Unicode icon symbol (ArialUnicode) ───────────────────────────────
DOMAIN_ICONS = {
    "light":         "\u2726",   # ✦  four-pointed star      (Dingbats)
    "switch":        "\u25CF",   # ●  black circle            (Geometric Shapes)
    "input_boolean": "\u25A3",   # ▣  white sq w/ black sq   (Geometric Shapes)
    "fan":           "\u2299",   # ⊙  circled dot operator   (Math Operators)
    "cover":         "\u2195",   # ↕  up-down arrow          (Arrows)
    "scene":         "\u2605",   # ★  black star             (Misc Symbols)
    "script":        "\u25B6",   # ▶  play triangle          (Geometric Shapes)
}

# ── Domains shown on screen ───────────────────────────────────────────────────
SUPPORTED_DOMAINS = set(DOMAIN_ICONS.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Base card
# ─────────────────────────────────────────────────────────────────────────────
class HADeviceCard(BoxLayout):
    """Shared properties and the non-blocking HA service call helper."""
    theme = Theme()

    entity_id   = StringProperty("")
    entity_name = StringProperty("Unknown")
    domain      = StringProperty("")
    domain_icon = StringProperty("")
    state       = StringProperty("off")
    is_on       = BooleanProperty(False)
    focused     = BooleanProperty(False)    # True when the rotary encoder targets this card
    is_favorite = BooleanProperty(False)    # True when starred by the user

    card_color   = ColorProperty([0.10, 0.13, 0.19, 1.0])
    text_color   = ColorProperty([1.0, 1.0, 1.0, 0.90])
    accent_color = ColorProperty([0.36, 0.67, 1.0, 1.0])

    _programmatic = False   # True while we're updating ids ourselves
    _focus_callback = None  # Assigned by the screen to propagate touch-focus

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        t = Theme()
        self.text_color  = t.get_color(t.TEXT_PRIMARY)
        self.accent_color = t.get_color(t.ALERT_INFO)
        if t.mode == 1:   # dark
            self.card_color = [0.10, 0.13, 0.19, 1.0]
        else:
            self.card_color = [0.95, 0.96, 0.98, 1.0]

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self, entity_id, state_str, attributes):
        """Populate card from a Home Assistant state dict."""
        self.entity_id   = entity_id
        self.domain      = entity_id.split(".")[0] if "." in entity_id else ""
        self.domain_icon = DOMAIN_ICONS.get(self.domain, "?")
        self.entity_name = attributes.get("friendly_name", entity_id)
        self.is_favorite = entity_id in load_ha_favorites()
        self._programmatic = True
        self._set_state_props(state_str, attributes)
        self._programmatic = False

    def toggle_favorite(self):
        """Flip the favorite state and persist."""
        favs = load_ha_favorites()
        if self.is_favorite:
            favs.discard(self.entity_id)
        else:
            favs.add(self.entity_id)
        save_ha_favorites(favs)
        self.is_favorite = not self.is_favorite

    def _on_self_touched(self):
        """Called when the card surface is touched — notifies the screen to move focus here."""
        if self._focus_callback is not None:
            self._focus_callback(self)

    def update_state(self, state_str, attributes):
        """Called from the HA listener — always on the main Kivy thread via Clock."""
        self._programmatic = True
        self._set_state_props(state_str, attributes)
        self._programmatic = False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _set_state_props(self, state_str, attributes):
        self.state = state_str
        self.is_on = state_str in ("on", "open", "playing", "home", "unlocked")

    def _send_service(self, service, data=None):
        if not HOME_ASSISTANT.ha_is_available:
            PIHOME_LOGGER.warn("HADeviceCard: HA not available, skipping service call")
            return
        if data is None:
            data = {}
        domain = self.domain
        eid    = self.entity_id

        def _do():
            try:
                HOME_ASSISTANT.update_service(domain, service, eid, data)
            except Exception as e:
                PIHOME_LOGGER.error(f"HADeviceCard: service call failed: {e}")

        Thread(target=_do, daemon=True).start()

    def do_toggle(self):
        """Called by rotary press — toggles the main switch if present."""
        if "main_switch" in self.ids:
            # _programmatic=False lets the on_enabled callback fire and call the API
            self._programmatic = False
            self.ids.main_switch.enabled = not self.is_on


# ─────────────────────────────────────────────────────────────────────────────
# Light card  (on/off switch + brightness slider)
# ─────────────────────────────────────────────────────────────────────────────
class HALightCard(HADeviceCard):
    brightness_pct      = NumericProperty(0.0)
    supports_brightness = BooleanProperty(True)
    _debounce_event     = None

    def _set_state_props(self, state_str, attributes):
        super()._set_state_props(state_str, attributes)
        raw = attributes.get("brightness")
        self.supports_brightness = raw is not None
        self.brightness_pct = round(raw / 255.0 * 100.0) if raw is not None else 0.0
        # Sync child widgets without triggering API callbacks
        if "main_switch" in self.ids:
            self.ids.main_switch.enabled = self.is_on
        if "brightness_slider" in self.ids:
            self.ids.brightness_slider.value = self.brightness_pct

    def _on_switch_touch(self, value):
        if self._programmatic:
            return
        self._send_service("turn_on" if value else "turn_off")

    def _on_slider_change(self, value):
        if self._programmatic:
            return
        self.brightness_pct = value
        # Debounce: wait 400 ms after the user stops dragging
        if self._debounce_event:
            self._debounce_event.cancel()
        self._debounce_event = Clock.schedule_once(
            lambda dt: self._send_brightness(value), 0.4
        )

    def _send_brightness(self, pct):
        brightness = max(1, min(255, int(pct / 100.0 * 255)))
        self._send_service("turn_on", {"brightness": brightness})

    def adjust_brightness(self, delta: float):
        """Nudge brightness by *delta* (positive = brighter) — called from rotary encoder."""
        if not self.supports_brightness:
            return
        new_val = max(0.0, min(100.0, self.brightness_pct + delta))
        self._programmatic = True
        self.brightness_pct = new_val
        if "brightness_slider" in self.ids:
            self.ids.brightness_slider.value = new_val
        self._programmatic = False
        if self._debounce_event:
            self._debounce_event.cancel()
        self._debounce_event = Clock.schedule_once(
            lambda dt: self._send_brightness(new_val), 0.4
        )


# ─────────────────────────────────────────────────────────────────────────────
# Toggle card  (switch / input_boolean / fan)
# ─────────────────────────────────────────────────────────────────────────────
class HAToggleCard(HADeviceCard):
    def _set_state_props(self, state_str, attributes):
        super()._set_state_props(state_str, attributes)
        if "main_switch" in self.ids:
            self.ids.main_switch.enabled = self.is_on

    def _on_switch_touch(self, value):
        if self._programmatic:
            return
        self._send_service("turn_on" if value else "turn_off")


# ─────────────────────────────────────────────────────────────────────────────
# Cover card  (cover / blind / garage door — open + close buttons)
# ─────────────────────────────────────────────────────────────────────────────
class HACoverCard(HADeviceCard):
    def _cover_open(self):
        self._send_service("open_cover")

    def _cover_close(self):
        self._send_service("close_cover")


# ─────────────────────────────────────────────────────────────────────────────
# Trigger card  (scene / script — single "Run" button)
# ─────────────────────────────────────────────────────────────────────────────
class HATriggerCard(HADeviceCard):
    def _trigger_run(self):
        self._send_service("turn_on")


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────
def make_ha_card(entity_id, state_dict):
    """Return the correct HADeviceCard subclass for *entity_id*, or None."""
    state_str  = state_dict.get("state", "off")
    attributes = state_dict.get("attributes", {})
    domain     = entity_id.split(".")[0] if "." in entity_id else ""

    if domain == "light":
        card = HALightCard()
    elif domain in ("switch", "input_boolean", "fan"):
        card = HAToggleCard()
    elif domain == "cover":
        card = HACoverCard()
    elif domain in ("scene", "script"):
        card = HATriggerCard()
    else:
        return None

    card.load(entity_id, state_str, attributes)
    return card
