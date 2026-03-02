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
import time
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (BooleanProperty, ColorProperty, ListProperty,
                              NumericProperty, StringProperty)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import AsyncImage  # noqa — referenced in hadevicecard.kv

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
    "climate":       "\u2600",   # ☀  sun / temperature      (Misc Symbols)
    "media_player":  "\u266B",   # ♫  beamed musical notes   (Misc Symbols)
}

# ── Domains shown on screen ───────────────────────────────────────────────────
SUPPORTED_DOMAINS = set(DOMAIN_ICONS.keys())

# ── Climate HVAC action → accent colour ──────────────────────────────────────
HVAC_ACTION_COLORS = {
    "heating":    [1.0,  0.45, 0.15, 1.0],
    "preheating": [1.0,  0.65, 0.30, 1.0],
    "cooling":    [0.15, 0.65, 1.0,  1.0],
    "drying":     [0.60, 0.85, 0.30, 1.0],
    "fan":        [0.65, 0.65, 1.0,  1.0],
    "idle":       [0.55, 0.55, 0.55, 1.0],
    "off":        [0.35, 0.35, 0.35, 1.0],
}
_HVAC_DEFAULT_COLOR = [0.55, 0.55, 0.55, 1.0]


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
    _debounce_event          = None
    _brightness_locked_until = 0.0   # monotonic deadline: ignore HA echoes until this time

    def _lock_brightness(self, duration: float = 2.0):
        """Block incoming WS brightness/slider updates for *duration* seconds."""
        self._brightness_locked_until = time.monotonic() + duration

    def _set_state_props(self, state_str, attributes):
        super()._set_state_props(state_str, attributes)
        raw = attributes.get("brightness")
        # When the light is ON we know for sure whether it's dimmable.
        # When it's OFF, HA omits brightness regardless — preserve the last known value.
        if raw is not None:
            self.supports_brightness = True
        elif state_str == "on":
            self.supports_brightness = False
        # Always sync the on/off switch
        if "main_switch" in self.ids:
            self.ids.main_switch.enabled = self.is_on
        # Only overwrite brightness while the user is NOT actively adjusting
        if time.monotonic() >= self._brightness_locked_until:
            self.brightness_pct = round(raw / 255.0 * 100.0) if raw is not None else 0.0
            if "brightness_slider" in self.ids:
                self.ids.brightness_slider.value = self.brightness_pct

    def _on_switch_touch(self, value):
        if self._programmatic:
            return
        if value:
            # If slider is at zero, turn on at 1% so HA doesn't jump to 100%
            if self.brightness_pct == 0.0:
                self._lock_brightness(2.0)
                self._programmatic = True
                self.brightness_pct = 1.0
                if "brightness_slider" in self.ids:
                    self.ids.brightness_slider.value = 1.0
                self._programmatic = False
                self._send_service("turn_on", {"brightness": 1})
            else:
                self._send_service("turn_on")
        else:
            self._send_service("turn_off")

    def _on_slider_change(self, value):
        if self._programmatic:
            return
        self._lock_brightness(2.0)   # suppress HA echo for 2 s
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
        # Rotating down on an already-off light does nothing
        if not self.is_on and delta <= 0:
            return
        self._lock_brightness(2.0)   # suppress HA echo for 2 s
        # When light is off, start from 0 so delta itself becomes the initial brightness
        base = self.brightness_pct if self.is_on else 0.0
        new_val = max(0.0, min(100.0, base + delta))
        # Optimistically flip the light on in the UI if it was off
        if not self.is_on:
            self._programmatic = True
            self.is_on = True
            if "main_switch" in self.ids:
                self.ids.main_switch.enabled = True
            self._programmatic = False
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
# Climate card  (thermostat / HVAC — current temp display + target temp slider)
# ─────────────────────────────────────────────────────────────────────────────
class HAClimateCard(HADeviceCard):
    current_temp      = NumericProperty(0.0)
    target_temp       = NumericProperty(70.0)
    min_temp          = NumericProperty(50.0)
    max_temp          = NumericProperty(90.0)
    hvac_mode         = StringProperty("off")
    hvac_action       = StringProperty("off")
    hvac_action_color = ColorProperty([0.55, 0.55, 0.55, 1.0])
    temp_unit         = StringProperty("\u00b0F")   # °F
    available_modes   = ListProperty([])
    _debounce_event   = None
    _temp_locked_until = 0.0

    def _lock_temp(self, duration: float = 2.0):
        self._temp_locked_until = time.monotonic() + duration

    def _set_state_props(self, state_str, attributes):
        # For climate entities, state IS the hvac_mode (heat/cool/off/auto…)
        self.hvac_mode = state_str
        self.state     = state_str
        self.is_on     = state_str != "off"
        action = attributes.get("hvac_action", state_str)
        self.hvac_action       = action
        self.hvac_action_color = list(HVAC_ACTION_COLORS.get(action, _HVAC_DEFAULT_COLOR))
        raw_cur = attributes.get("current_temperature")
        if raw_cur is not None:
            self.current_temp = float(raw_cur)
        self.available_modes = list(attributes.get("hvac_modes", []))
        self.min_temp = float(attributes.get("min_temp", 50.0))
        self.max_temp = float(attributes.get("max_temp", 90.0))
        unit = attributes.get("temperature_unit", "\u00b0F")
        self.temp_unit = unit if unit else "\u00b0F"
        if time.monotonic() >= self._temp_locked_until:
            raw_tgt = attributes.get("temperature")
            if raw_tgt is not None:
                self.target_temp = float(raw_tgt)
                if "temp_slider" in self.ids:
                    span = max(0.1, self.max_temp - self.min_temp)
                    pct  = (self.target_temp - self.min_temp) / span * 100.0
                    self.ids.temp_slider.value = max(0.0, min(100.0, pct))

    def _on_temp_slider_change(self, value):
        if self._programmatic:
            return
        self._lock_temp(2.0)
        span = max(0.1, self.max_temp - self.min_temp)
        self.target_temp = self.min_temp + value / 100.0 * span
        if self._debounce_event:
            self._debounce_event.cancel()
        tgt = self.target_temp
        self._debounce_event = Clock.schedule_once(
            lambda dt: self._send_service("set_temperature", {"temperature": round(tgt, 1)}), 0.4
        )

    def adjust_brightness(self, delta: float):
        """Rotary encoder: nudge target temperature ±0.5° per notch."""
        step = 0.5 if delta > 0 else -0.5
        self._lock_temp(2.0)
        new_temp = max(self.min_temp, min(self.max_temp, self.target_temp + step))
        self.target_temp = new_temp
        if "temp_slider" in self.ids:
            span = max(0.1, self.max_temp - self.min_temp)
            pct  = (new_temp - self.min_temp) / span * 100.0
            self._programmatic = True
            self.ids.temp_slider.value = max(0.0, min(100.0, pct))
            self._programmatic = False
        if self._debounce_event:
            self._debounce_event.cancel()
        self._debounce_event = Clock.schedule_once(
            lambda dt: self._send_service("set_temperature", {"temperature": round(new_temp, 1)}), 0.4
        )

    def do_toggle(self):
        """Rotary press: cycle to the next HVAC mode."""
        modes = [m for m in self.available_modes if m]
        if not modes:
            return
        try:
            idx       = modes.index(self.hvac_mode)
            next_mode = modes[(idx + 1) % len(modes)]
        except ValueError:
            next_mode = modes[0]
        self.hvac_mode = next_mode
        self.is_on     = next_mode != "off"
        self._send_service("set_hvac_mode", {"hvac_mode": next_mode})


# ─────────────────────────────────────────────────────────────────────────────
# Media player card  (now-playing info + thumbnail + transport controls)
# ─────────────────────────────────────────────────────────────────────────────
class HAMediaCard(HADeviceCard):
    media_title   = StringProperty("")
    media_artist  = StringProperty("")
    media_state   = StringProperty("off")
    volume_pct    = NumericProperty(0.0)     # 0–100
    media_img_url = StringProperty("")
    is_playing    = BooleanProperty(False)

    _debounce_event      = None
    _volume_locked_until = 0.0

    def _lock_volume(self, duration: float = 2.0):
        self._volume_locked_until = time.monotonic() + duration

    def _set_state_props(self, state_str, attributes):
        self.state       = state_str
        self.media_state = state_str
        self.is_on       = state_str not in ("off", "unavailable", "unknown")
        self.is_playing  = state_str == "playing"
        self.media_title  = attributes.get("media_title", "")
        self.media_artist = (
            attributes.get("media_artist", "")
            or attributes.get("media_album_name", "")
            or attributes.get("app_name", "")
        )
        # Thumbnail — entity_picture is a relative /api/... path served by HA
        ep = attributes.get("entity_picture", "")
        if ep:
            base = HOME_ASSISTANT.HA_URL
            if base.endswith("/api"):
                base = base[:-4]
            self.media_img_url = base + ep
        else:
            self.media_img_url = ""
        # Volume (suppress WS echo while user is adjusting)
        if time.monotonic() >= self._volume_locked_until:
            vol_raw = attributes.get("volume_level")
            if vol_raw is not None:
                self.volume_pct = round(float(vol_raw) * 100.0)
                if "volume_slider" in self.ids:
                    self._programmatic = True
                    self.ids.volume_slider.value = self.volume_pct
                    self._programmatic = False

    def _play_pause(self):
        self._send_service("media_pause" if self.is_playing else "media_play")

    def _prev_track(self):
        self._send_service("media_previous_track")

    def _next_track(self):
        self._send_service("media_next_track")

    def _on_volume_change(self, value):
        if self._programmatic:
            return
        self._lock_volume(2.0)
        self.volume_pct = value
        if self._debounce_event:
            self._debounce_event.cancel()
        self._debounce_event = Clock.schedule_once(
            lambda dt: self._send_service(
                "volume_set", {"volume_level": round(value / 100.0, 2)}
            ), 0.4
        )

    def adjust_brightness(self, delta: float):
        """Rotary encoder: adjust volume ±5% per notch."""
        self._lock_volume(2.0)
        new_vol = max(0.0, min(100.0, self.volume_pct + delta))
        self.volume_pct = new_vol
        if "volume_slider" in self.ids:
            self._programmatic = True
            self.ids.volume_slider.value = new_vol
            self._programmatic = False
        if self._debounce_event:
            self._debounce_event.cancel()
        self._debounce_event = Clock.schedule_once(
            lambda dt: self._send_service(
                "volume_set", {"volume_level": round(new_vol / 100.0, 2)}
            ), 0.4
        )

    def do_toggle(self):
        """Rotary press: play / pause."""
        self._play_pause()


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
    elif domain == "climate":
        card = HAClimateCard()
    elif domain == "media_player":
        card = HAMediaCard()
    else:
        return None

    card.load(entity_id, state_str, attributes)
    return card
