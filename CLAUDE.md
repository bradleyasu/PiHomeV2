# PiHome — Screen Creation Guide

This document is used by Claude to create new PiHome screens. PiHome is a Kivy 2.0.0 touchscreen application targeting Raspberry Pi 3+ (default resolution 800x480, configurable). Screens are discovered at runtime via manifest files — no changes to `main.py` are needed.

---

## Screen Creation Workflow

When a user asks for a new screen (e.g., "I need a screen that does X"), follow this workflow:

### Step 1: Gather Requirements

Before writing any code, ask the user these questions (skip any that are already obvious from their request):

1. **Screen name/label** — What should it be called in the app menu? (e.g., "Weather", "Stocks")
2. **Data sources** — What APIs, protocols, or data does it need? (REST API URLs, MQTT, WebSocket, local data, etc.)
3. **User-configurable settings** — What should users be able to change in the Settings panel? (API keys, refresh intervals, IP addresses, toggle features, etc.)
4. **Update frequency** — Does it need real-time updates? How often? (polling interval, push-based, on-demand)
5. **UI layout preferences** — Any specific layout ideas? (cards, lists, charts, split-panel, full-screen, etc.)
6. **Rotary encoder behavior** — Should the physical knob do anything custom? (cycle pages, scroll, adjust values, etc.)
7. **PIN protection** — Should this screen require a PIN to access?
8. **Dark/light mode** — Should it fully respect the system theme, or does it have its own visual identity?

### Step 2: Propose a Plan

Summarize the screen's structure, settings, file layout, and behavior. Get confirmation before writing code.

### Step 3: Scaffold All Files

Create the complete screen directory with all required files (see structure below).

### Step 4: Inform the User

After creating the screen, remind them to:
- Replace `icon.png` in the screen directory with their own 100x100px PNG icon
- Configure any required settings (API keys, etc.) in the PiHome Settings panel
- Install any pip dependencies if needed

---

## Screen Directory Structure

Every screen lives in its own directory under `screens/`:

```
screens/
└── MyScreen/
    ├── manifest.json      # Screen metadata & settings definitions
    ├── myscreen.py        # Python class (lowercase filename)
    ├── myscreen.kv        # Kivy layout (lowercase filename)
    ├── icon.png           # Screen icon (user replaces this)
    ├── audio/             # Optional: screen-specific sound effects
    │   └── example.mp3
    └── events/            # Optional: screen-specific PihomeEvent subclasses
        └── myevent.py
```

**Naming conventions:**
- Directory name: PascalCase (e.g., `MyScreen`)
- Python/KV filenames: lowercase (e.g., `myscreen.py`, `myscreen.kv`)
- Class name: PascalCase + "Screen" suffix (e.g., `MyScreenScreen`)

---

## Manifest Format (`manifest.json`)

```json
{
    "module": "MyScreen.myscreen",
    "name": "MyScreenScreen",
    "id": "_myscreen",
    "label": "My Screen",
    "settingsLabel": "My Screen",
    "settingsIndex": 50,
    "description": "Brief description of what this screen does",
    "hidden": false,
    "requires_pin": false,
    "index": 50,
    "icon": "screens/MyScreen/icon.png",
    "settings": []
}
```

**Required fields:**
| Field | Type | Description |
|-------|------|-------------|
| `module` | string | `"<DirName>.<filename>"` — Python module path |
| `name` | string | Class name (must match the Python class exactly) |
| `id` | string | Unique ID, conventionally prefixed with `_` |
| `label` | string | Display name shown in the app menu |
| `description` | string | Brief description |
| `hidden` | bool | If `true`, hidden from the app menu |
| `requires_pin` | bool | If `true`, PIN entry required to access |
| `index` | int | Menu sort order (lower = first, Settings uses 1000) |
| `icon` | string | Relative path from project root to icon PNG |
| `settings` | array | Settings definitions (see below) |

**Optional fields:**
| Field | Type | Description |
|-------|------|-------------|
| `settingsLabel` | string | Alternate label for Settings panel (defaults to `label`) |
| `settingsIndex` | int | Settings panel sort order (default 9999) |
| `disabled` | bool | If `true`, screen is not loaded at all |

### Settings Types

Settings defined here are automatically rendered in the PiHome Settings screen. No additional UI code is needed.

**Title** (section separator):
```json
{ "type": "title", "title": "Connection Settings" }
```

**String** (text input):
```json
{
    "type": "string",
    "title": "API Key",
    "desc": "Your API key from the service dashboard",
    "section": "myscreen",
    "key": "api_key"
}
```

**Numeric** (number input):
```json
{
    "type": "numeric",
    "title": "Refresh Interval",
    "desc": "How often to update data (seconds)",
    "section": "myscreen",
    "key": "refresh_interval"
}
```

**Boolean** (toggle switch):
```json
{
    "type": "bool",
    "title": "Enable Notifications",
    "desc": "Show toast notifications on updates",
    "section": "myscreen",
    "key": "notifications_enabled"
}
```

**Options** (dropdown):
```json
{
    "type": "options",
    "title": "Temperature Unit",
    "desc": "Display temperature in Fahrenheit or Celsius",
    "section": "myscreen",
    "key": "temp_unit",
    "options": ["Fahrenheit", "Celsius"]
}
```

The `section` and `key` fields map to the INI config file (`base.ini`). Use a consistent section name for your screen (e.g., `"myscreen"`).

---

## Python Screen Class Template

```python
import threading

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import (
    ColorProperty, StringProperty, NumericProperty,
    BooleanProperty, ObjectProperty,
)

from interface.pihomescreen import PiHomeScreen
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

# Load KV layout — must happen at module level, before class definition
Builder.load_file("./screens/MyScreen/myscreen.kv")


class MyScreenScreen(PiHomeScreen):
    """One-line description of this screen."""

    # ── Theme colors ──
    # These property names are recognized by on_config_update() in the base
    # class and are automatically synced to the current theme (dark/light).
    bg_color     = ColorProperty([0.10, 0.10, 0.12, 1])
    header_color = ColorProperty([0.14, 0.14, 0.16, 1])
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([1, 1, 1, 0.45])
    accent_color = ColorProperty([0.25, 0.52, 1.0, 1])
    status_color = ColorProperty([0.45, 0.45, 0.45, 1])

    # Optional derived colors (auto-calculated if defined):
    # card_color    = ColorProperty(...)  # header_color with 0.85 alpha
    # sidebar_color = ColorProperty(...)  # header_color * 0.80
    # divider_color = ColorProperty(...)  # header_color * 0.60
    # row_bg_color  = ColorProperty(...)  # header_color with 0.70 alpha

    # ── Screen-specific properties ──
    # Define StringProperty, NumericProperty, etc. here for KV bindings.
    # Example:
    # title_text = StringProperty("Hello")
    # value = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize threading primitives
        self._stop_event = threading.Event()
        self._thread = None
        self._load_config()

    # ── Configuration ──

    def _load_config(self):
        """Read settings from base.ini. Called on init, enter, and config update."""
        self._api_key = CONFIG.get("myscreen", "api_key", "").strip()
        self._refresh = max(10, CONFIG.get_int("myscreen", "refresh_interval", 60))
        # For boolean settings:
        # self._enabled = CONFIG.get("myscreen", "enabled", "0").strip().lower() in ("1", "true")

    def on_config_update(self, config):
        """Called when any setting changes. Reload config and reconnect if needed."""
        old_key = self._api_key
        self._load_config()
        # If the screen is active and settings changed, restart connections
        if self.is_open and self._api_key != old_key:
            self._stop_work()
            Clock.schedule_once(lambda dt: self._start_work(), 0.5)
        # IMPORTANT: call super() LAST — it applies theme colors
        super().on_config_update(config)

    # ── Lifecycle ──

    def on_enter(self, *args):
        self._load_config()
        self._start_work()
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        self._stop_work()
        return super().on_pre_leave(*args)

    # ── Background work ──

    def _start_work(self):
        """Start background thread or polling."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="myscreen-worker"
        )
        self._thread.start()

    def _stop_work(self):
        """Signal background thread to stop."""
        self._stop_event.set()

    def _worker(self):
        """Background thread — fetch data, push to main thread via Clock."""
        while not self._stop_event.is_set():
            try:
                # Do work here (API calls, data processing, etc.)
                data = {"example": "value"}

                # Push results to main thread for UI update
                Clock.schedule_once(lambda dt, d=data: self._apply_data(d), 0)
            except Exception as e:
                PIHOME_LOGGER.error(f"MyScreen: worker error: {e}")

            # Wait for next cycle (use Event.wait, NOT time.sleep)
            self._stop_event.wait(self._refresh)

    def _apply_data(self, data):
        """Apply fetched data to UI properties (runs on main thread)."""
        # self.title_text = data.get("example", "")
        pass

    # ── Rotary encoder (optional overrides) ──

    def on_rotary_turn(self, direction, button_pressed):
        """Called on knob turn. direction: 1 (clockwise) or -1 (counter-clockwise)."""
        # Example: cycle through pages
        # self.current_page = (self.current_page + direction) % self.total_pages
        return True  # True = consumed, False = fall through to default (volume)

    def on_rotary_pressed(self):
        """Called on short knob press."""
        # Example: refresh data
        # self._stop_work()
        # self._start_work()
        return True  # True = consumed, False = fall through to default (toggle audio)

    def on_rotary_long_pressed(self):
        """Called on long knob press (~0.7s)."""
        self.go_back()
        return True
```

### Key Patterns

**Property observers for formatted display strings:**
```python
# Avoid f-strings in KV files — they break on Python 3.12+.
# Instead, compute formatted strings in Python:
temp_value = NumericProperty(0.0)
temp_text = StringProperty("--°C")

def on_temp_value(self, inst, val):
    self.temp_text = f"{val:.1f}°C"
# Then in KV: text: root.temp_text
```

**Using the POLLER for simple API polling (alternative to threads):**
```python
from networking.poller import POLLER

def on_enter(self, *args):
    self._poll_id = POLLER.register_api(
        "https://api.example.com/data",
        interval=60,
        on_resp=self._on_data
    )
    return super().on_enter(*args)

def on_pre_leave(self, *args):
    POLLER.unregister_api(self._poll_id)
    return super().on_pre_leave(*args)

def _on_data(self, result):
    # result is the parsed JSON response
    self.some_property = result.get("value", "")
```

**Toast notifications:**
```python
from util.helpers import toast
toast("Data updated!", "info", 3)   # levels: "info", "warning", "error", "success"
```

**Screen-specific sound effects:**

Screens can include custom audio by adding an `audio/` subdirectory with `.mp3`, `.wav`, or `.ogg` files. These are automatically discovered at startup and namespaced as `screendir.filename` (lowercase directory name, no extension).

```
screens/MyScreen/audio/alarm.mp3  →  key: "myscreen.alarm"
screens/MyScreen/audio/done.wav   →  key: "myscreen.done"
```

```python
from services.audio.sfx import SFX
SFX.play("myscreen.alarm")     # Play once
SFX.loop("myscreen.alarm")     # Loop until stopped
SFX.stop("myscreen.alarm")     # Stop playback
```

Global sound effects in `assets/audio/sfx/` are available without a prefix (e.g., `SFX.play("alert")`).

**Screen-specific events:**

Screens can include custom PiHome events by adding an `events/` subdirectory with `.py` files that extend `PihomeEvent`. These are automatically discovered by the event factory and become available via all entry points (MQTT, HTTP, WebSocket).

```
screens/MyScreen/events/myevent.py
```

```python
from events.pihomeevent import PihomeEvent

class MyScreenEvent(PihomeEvent):
    type = "myscreen_action"  # Prefix with screen name to avoid collisions

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        return {"code": 200, "body": {"status": "success", "message": "Done"}}
```

- Screen events use the same `PihomeEvent` base class and contract as global events
- No manifest changes are needed — events are discovered by class introspection (the `type` attribute)
- Global events take precedence on type conflicts (a warning is logged and the screen event is skipped)
- Prefix event types with the screen name (e.g., `myscreen_action`) to avoid collisions with global or other screen events

**Boolean config values** are stored as strings in `base.ini`:
```python
enabled = CONFIG.get("section", "key", "0").strip().lower() in ("1", "true")
```

---

## KV Layout Template

```kv
#:kivy 2.0.0
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<MyScreenScreen>:
    canvas.before:
        Color:
            rgba: root.bg_color
        Rectangle:
            size: self.size
            pos: self.pos

    BoxLayout:
        orientation: "vertical"
        size_hint: 1, 1

        # ── Header ──────────────────────────────────────────────────────
        BoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(44)
            padding: dp(54), 0, dp(10), 0
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: root.header_color
                Rectangle:
                    size: self.size
                    pos: self.pos
                # Subtle bottom border
                Color:
                    rgba: 1, 1, 1, 0.06
                Rectangle:
                    size: self.width, dp(1)
                    pos: self.x, self.y

            # Screen icon (MaterialIcons)
            Label:
                text: "\ue88a"
                font_name: "MaterialIcons"
                font_size: sp(20)
                color: root.accent_color
                size_hint_x: None
                width: dp(26)
                halign: "center"
                valign: "middle"

            # Screen title
            Label:
                text: "MY SCREEN"
                font_name: "Nunito"
                font_size: sp(12)
                bold: True
                color: root.text_color
                size_hint_x: None
                width: self.texture_size[0]
                halign: "left"
                valign: "middle"
                text_size: self.size

            # Spacer
            Widget:

            # Optional: status indicator dot
            Widget:
                size_hint: None, None
                size: dp(8), dp(8)
                pos_hint: {"center_y": 0.5}
                canvas:
                    Color:
                        rgba: root.status_color
                    Ellipse:
                        pos: self.pos
                        size: self.size

        # ── Body ────────────────────────────────────────────────────────
        BoxLayout:
            orientation: "vertical"
            padding: dp(16)
            spacing: dp(8)

            Label:
                text: "Screen content goes here"
                font_name: "Nunito"
                font_size: sp(16)
                color: root.text_color
                halign: "center"
                valign: "middle"
                text_size: self.size
```

### KV Rules

1. **Always start with** `#:kivy 2.0.0` and import `dp`/`sp`
2. **NO f-strings in KV** — use pre-computed `StringProperty` values from Python
3. **Header left padding: `dp(54)`** — clears the hamburger menu overlay (40dp icon + padding at top-left)
4. **Use `dp()` for all sizes/positions**, `sp()` for all font sizes
5. **Fonts:** `Nunito` (body text), `MaterialIcons` (icon glyphs), `ArialUnicode` (extended characters)
6. **Background colors** — use `canvas.before` with `Color` + `Rectangle`, not widget `background_color`
7. **Text alignment** — `halign`/`valign` require `text_size: self.size` to take effect
8. **Reference screen properties** with `root.property_name`

### Common UI Patterns

**Divider line:**
```kv
Widget:
    size_hint_y: None
    height: dp(1)
    canvas:
        Color:
            rgba: 1, 1, 1, 0.07
        Rectangle:
            size: self.size
            pos: self.pos
```

**Scrollable content:**
```kv
ScrollView:
    do_scroll_x: False
    bar_width: dp(3)
    bar_color: root.accent_color
    scroll_type: ['bars', 'content']

    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: self.minimum_height
        spacing: dp(4)
        # Children go here
```

**Card with rounded corners:**
```kv
BoxLayout:
    orientation: "vertical"
    padding: dp(12)
    canvas.before:
        Color:
            rgba: root.card_color
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(8)]
```

**Conditional visibility (hide/show):**
```kv
BoxLayout:
    opacity: 1 if root.show_section else 0
    disabled: not root.show_section
    # Note: opacity 0 still takes space. For true removal, manage in Python.
```

**MaterialIcons** — use Unicode codepoints. Find icons at fonts.google.com/icons, then use the codepoint:
```kv
Label:
    text: "\ue88a"
    font_name: "MaterialIcons"
```

---

## Theme System

Screens automatically support dark/light mode via standard `ColorProperty` names. The base class `on_config_update()` maps these property names to theme tokens:

| Property | Theme Token | Purpose |
|----------|-------------|---------|
| `bg_color` | `BACKGROUND_PRIMARY` | Main background |
| `header_color` | `BACKGROUND_SECONDARY` | Header/toolbar background |
| `text_color` | `TEXT_PRIMARY` | Primary text |
| `muted_color` | `TEXT_SECONDARY` | Secondary/dimmed text |
| `accent_color` | `ALERT_INFO` | Accent highlights |
| `status_color` | `TEXT_SECONDARY` | Status indicators |

**Derived colors** (auto-calculated if the property exists on your class):
| Property | Derivation |
|----------|------------|
| `card_color` | `header_color` RGB with 0.85 alpha |
| `sidebar_color` | `header_color` RGB * 0.80 |
| `divider_color` | `header_color` RGB * 0.60 |
| `row_bg_color` | `header_color` RGB with 0.70 alpha |

**For custom colors beyond the standard set:**
```python
from theme.theme import Theme

def on_config_update(self, config):
    th = Theme()
    self.danger_color = th.get_color(th.ALERT_DANGER)
    self.success_color = th.get_color(th.ALERT_SUCCESS)
    super().on_config_update(config)
```

**Available theme tokens:**
- Backgrounds: `BACKGROUND_PRIMARY`, `BACKGROUND_SECONDARY`
- Text: `TEXT_PRIMARY`, `TEXT_SECONDARY`, `TEXT_DANGER`, `TEXT_SUCCESS`
- Buttons: `BUTTON_PRIMARY`, `BUTTON_SECONDARY`, `BUTTON_DANGER`, `BUTTON_SUCCESS`
- Alerts: `ALERT_DANGER`, `ALERT_WARNING`, `ALERT_INFO`, `ALERT_SUCCESS`
- Switch: `SWITCH_ACTIVE`, `SWITCH_INACTIVE`

Some screens may have their own brand identity (e.g., BambuLab uses a specific green accent). This is fine — not every screen must use the standard theme accent, but backgrounds and text should still respect dark/light mode when possible.

---

## Available Components

Reusable widgets in the `components/` directory:

| Component | Import | Purpose |
|-----------|--------|---------|
| `PiTextInput` | `from components.Keyboard.keyboard import PiTextInput` | Text input with on-screen virtual keyboard (use instead of Kivy `TextInput` for touch/Pi) |
| `CircleButton` | `from components.Button.circlebutton import CircleButton` | Circular icon button with ripple animation |
| `NetworkImage` | `from components.Image.networkimage import NetworkImage` | Image widget that loads from a URL |
| `Toast` | `from util.helpers import toast` | Notification popup: `toast("msg", "info", 3)` |
| `Switch` | `from components.Switch.switch import PiSwitch` | Toggle switch widget |
| `NumberStepper` | `from components.NumberStepper.numberstepper import NumberStepper` | Increment/decrement number input |
| `DatePicker` | `from components.DatePicker.datepicker import DatePicker` | Date selection widget |
| `Slider` | `from components.Slider.` | Custom slider controls |
| `VideoPlayer` | `from components.VideoPlayer.` | Video playback widget |

---

## Performance Constraints

PiHome must run on Raspberry Pi 3+ (quad-core ARM, 1GB RAM). Keep these rules in mind:

- **Never block the main thread** — all network calls, file I/O, and heavy computation must run in background threads
- **Use `threading.Event.wait(interval)`** instead of `time.sleep()` — this allows clean shutdown
- **Use daemon threads** (`daemon=True`) so they don't prevent app exit
- **Minimize texture/image allocations** — reuse `Texture` objects when possible (see BambuLab camera pattern)
- **Be mindful of polling frequency** — don't poll faster than needed (60s is a good default for most APIs)
- **Avoid unnecessary widget rebuilds** — use property bindings instead of clearing and recreating widgets

---

## Anti-Patterns and Gotchas

1. **No f-strings in KV files** — Kivy's parser breaks on Python 3.12+. Use `StringProperty` computed in Python instead.
2. **`super().on_config_update(config)` must be called LAST** — it applies theme colors, which should happen after your custom config logic.
3. **`super().on_enter()` and `super().on_pre_leave()` must be called** — they manage `is_open` state and screen tracking.
4. **Always stop threads in `on_pre_leave`** — failing to do so causes resource leaks and stale UI updates.
5. **Lambda variable capture** — use default args: `lambda dt, x=x: func(x)`, NOT `lambda dt: func(x)`.
6. **Boolean configs are strings** — check with `.strip().lower() in ("1", "true")`.
7. **Don't use `time.sleep()` in threads** — use `self._stop_event.wait(seconds)` for interruptible waits.
8. **`text_size: self.size`** is required in KV for `halign`/`valign` to work on Labels.
9. **MaterialIcons** Always make sure that icons are used correctly and fonts are not mixed. Attempting to reference a MaterialIcon from a label with a different font will not work. 

---

## Reference: Existing Screens

Use these as examples when building new screens:

- **BambuLab** (`screens/BambuLab/`) — Full-featured: MQTT, camera streaming, threading, multi-page stats, rotary encoder, property observers
- **Home** (`screens/Home/`) — Animations, gestures, multiple widgets, wallpaper management
- **MusicPlayer** (`screens/MusicPlayer/`) — Audio playback, shaders, carousel, drawer animation
- **Cocktail** (`screens/Cocktail/`) — API-driven search, dynamic UI construction
- **Settings** (`screens/Settings/`) — Config panel rendering from manifests

---

## Quick Reference: File Paths

| Resource | Path |
|----------|------|
| Base screen class | `interface/pihomescreen.py` |
| Screen manager | `interface/pihomescreenmanager.py` |
| Theme system | `theme/theme.py` |
| Color definitions | `theme/color.py` |
| Configuration | `util/configuration.py` |
| Logger | `util/phlog.py` |
| Helpers (toast, get_app) | `util/helpers.py` |
| Poller | `networking/poller.py` |
| Virtual keyboard | `components/Keyboard/keyboard.py` |
| Event base class & factory | `events/pihomeevent.py` |
| Main app | `main.py` |
