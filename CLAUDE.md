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
- Declare any pip dependencies in the manifest's `dependencies` array (see below) —
  PiHome auto-installs missing ones at startup; no manual `pip install` needed

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
| `dependencies` | array | pip requirement strings for this screen's extra Python packages (see below) |

### Screen Dependencies (`dependencies`)

Declare any pip packages a screen needs beyond the core `requirements.txt`:

```json
"dependencies": ["zeroconf", "paho-mqtt==1.6.1"]
```

Entries are standard pip requirement specifiers (name, optional version pin/extras).
At startup PiHome scans every non-disabled manifest and **auto-installs any declared
dependency that isn't already present** (`util/dependencies.py`), so a screen is
drop-in: copy the directory in, restart, and its deps install themselves.

- Progress surfaces in the Notification Center: an "Installing dependencies"
  notification appears, then updates in place to success or failure.
- On Linux/Pi, pip runs with `--break-system-packages` automatically (omitted on macOS).
- **A restart is required to use a newly installed dependency.** A running process
  can't adopt a freshly pip-installed package (modules have already bound their
  import fallbacks, and startup-service singletons hold stale references). So after
  any successful install, a single batched "Restart required" notification appears —
  tapping it restarts PiHome (`reboot`/`restart_pihome` event). Set
  `[dependencies] auto_restart = 1` in `base.ini` to restart automatically instead
  of prompting (useful for unattended kiosks). The flow is self-terminating: after
  the restart the deps are present, so nothing reinstalls and no further prompt fires.
- Screens should still **degrade gracefully** when a dep is missing (lazy-import it
  inside methods and show a friendly message), since the install + restart happen
  after startup.
- Missing-package detection uses the *distribution* name (via `importlib.metadata`),
  so pip-name vs import-name mismatches (e.g. `paho-mqtt` → `paho.mqtt`) are fine.

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
from theme.theme import Theme
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

# Load KV layout — must happen at module level, before class definition
Builder.load_file("./screens/MyScreen/myscreen.kv")


class MyScreenScreen(PiHomeScreen):
    """One-line description of this screen."""

    # ── Theme colors ──
    # These property names are recognized by on_config_update() in the base class
    # and are automatically synced to the current theme (dark/light). Derive the
    # DEFAULTS from the theme too — screens are created lazily, so a hardcoded
    # literal would paint the wrong color on first open (see gotcha #13).
    _th = Theme()
    bg_color      = ColorProperty(_th.get_color(_th.BACKGROUND_PRIMARY))
    header_color  = ColorProperty(_th.get_color(_th.BACKGROUND_SECONDARY))
    text_color    = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color   = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    accent_color  = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))
    status_color  = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))

    # Optional derived colors (auto-calculated by the base class if defined):
    # card_color    = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    # row_bg_color  = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    # divider_color = ColorProperty(_th.get_color(_th.BACKGROUND_BORDER))
    # sidebar_color = ColorProperty(_th.get_color(_th.BACKGROUND_SECONDARY))

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
        super().on_enter(*args)
        self._load_config()
        # Apply the theme BEFORE building any widgets — a lazily-created screen
        # may have missed the startup reload_all() (gotcha #13). Widgets built
        # after this call pick up the correct colors.
        super().on_config_update(CONFIG)
        self._start_work()

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

**Screen-specific services:**

Some screens need an always-on background service that only that screen uses (e.g. a 24/7 power monitor that polls and fires alert events even when the screen isn't open). Such a service can live **inside the screen** under a `services/` subdirectory and be declared in the manifest, so it ships and is removed together with its screen — no `main.py` changes.

```
screens/MyScreen/services/myservice.py
```

Declare it in `manifest.json` with a `services` array of module names (no `.py`):

```json
"services": ["myservice"]
```

At startup PiHome imports each declared service module (`util/screen_services.py`, `load_screen_services()`), which starts it. A service is an informal **module-level singleton** that self-starts its work in `__init__` and exports a module-level instance:

```python
class MyService:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="myservice")
        self._thread.start()

    def shutdown(self):       # optional — called from the app's on_stop()
        self._stop.set()

MY_SERVICE = MyService()      # module-level singleton
```

- **Importing the module starts the service.** The screen and its event handlers reference the same instance by package path: `from screens.MyScreen.services.myservice import MY_SERVICE`. Because the loader imports by the **package path** (`importlib.import_module`), the loader and the screen share the **one** singleton — never load a service via `spec_from_file_location` (that creates a second instance/thread).
- **Shutdown is optional.** If the instance exposes `shutdown()` or `stop()`, the loader calls it on app exit; otherwise the `daemon=True` thread dies with the process.
- **Disabling/removing the screen removes the service** — disabled manifests are skipped, so the service never starts.
- **Degrade gracefully when a pip dependency is missing.** Declare deps in the manifest's `dependencies` array; they auto-install but require a restart, so wrap the import (`try/except`) and expose an `available` flag, since the first boot may run before the dep is present.

**User-defined automation rules — use `util/rulestore.py`, never hand-roll it:**

If your screen lets the user bind *"when X happens, fire this PiHome event"* (a printer
finishing, a power threshold, a button press), the persistence, validation, enable/disable,
cooldown, last-fired tracking, placeholder substitution and main-thread dispatch are already
written. Create one `RuleStore` and keep only your trigger detection:

```python
from util.rulestore import RuleStore

RULES = RuleStore(
    key="myscreen",                        # stable id, used by automations_list
    label="My Screen",                     # section header on the Automations screen
    path="cache/myscreen_rules.json",      # always under cache/ (gotcha #12)
    glyph="",                        # MaterialIcons codepoint for the row
    describe=lambda r: f"On {r['state']}",  # human text for the TRIGGER
    create_event="myscreen_state_alert",    # the event that creates one of these
)

# ... in your service, when the trigger actually occurs:
RULES.fire_matching("state", "FINISH", {"job": name, "progress": pct})
```

Your three management events then become one-liners over `RULES.upsert(rule, validate=...)`,
`RULES.list()` and `RULES.remove(rid)`. Do validation of your own fields in the `validate`
hook; the store already rejects a missing/malformed nested `event`.

- **Constructing a store registers it** in `util.rulestore.RULE_STORES`, which is what the
  **Automations** screen (`screens/Automations/`) and the `automations_list` event enumerate.
  Registration happens on import, so removing your screen directory simply removes its
  section — no screen imports another screen's service.
- **Rules gain `enabled` and `last_fired`** automatically, defaulted in on load, so an
  existing rules file is read unchanged.
- **`fire()` is fire-and-forget** and safe from any thread. Use **`fire_and_wait()`** only
  when you must return the action's own response to the caller (e.g. a manual "run this now"
  over HTTP).
- **Placeholders:** `substitute()` accepts named keys (`$job`, `$progress`) *and* positional
  `$1` (the older ShellEvent/Bluetooth convention). Pass `{"1": value}` for the latter.
- **Keying:** rules are keyed by `id` (auto-generated when omitted). Pass `key_fn` if your
  store needs a composite key — Bluetooth uses `device|command` so one token can be bound
  per-device with a `*` wildcard fallback.

Reference implementations: `screens/BambuLab/services/bambu_service.py` (simple state match),
`screens/EmporiumPower/services/emporia_service.py` (edge latch kept in its own state file),
`screens/BluetoothConnect/services/ble_service.py` (composite key). Tests:
`util/test_rulestore.py`.

**Where to put the store, and what the user gets:**

- **Create it in the *service* module, not the screen module.** The rules must be evaluated
  when the screen is closed — that is the entire point — and a service declared in the
  manifest's `services` array is imported at boot by `util/screen_services.py`. (A store
  defined at screen-module scope also registers at startup, since `load_screens()` imports
  every screen module eagerly, but then your trigger detection has nowhere to live.)
- **A `disabled: true` manifest skips the screen module entirely**, so its store never
  registers and its section disappears from Automations. Note screen **events** are still
  discovered for disabled screens, so gate any hardware behind an `enabled` config flag.
- **You get the Automations screen for free.** Constructing the store is the whole
  integration — listing, test-fire, enable/disable and delete all work with no UI code. Give
  `describe` and `glyph` some thought: `describe(rule)` is the user-facing sentence
  ("Printer goes COMPLETE", "Whole Home goes above 3000W"), and the action line beside it is
  generated by `describe_event()` from the stored event.
- **Always set `create_event`.** Rules can only be *created* by sending an event, so the
  Automations empty state lists every registered store's `create_event` by name — that list
  is the only place a user discovers what to send. Omit it and your screen silently stops
  telling anyone how to use it. It is also returned by `automations_list` for API clients.

**Event naming convention** — follow the existing trio so the API stays predictable:

| Purpose | Type | Notes |
|---------|------|-------|
| Create/update | `<screen>_<thing>_alert` | `id` optional; resending the same `id` updates |
| List | `<screen>_<thing>_alerts_list` | |
| Delete | `<screen>_<thing>_alert_remove` | 404 when the id doesn't exist |
| Test-fire (optional) | `<screen>_<thing>_test` | Very cheap, and the only way to verify a rule without waiting for the real trigger — worth adding |

Aggregated **read** across every store is already provided by the global `automations_list`
event; you don't write one. Note there is currently **no** event for enable/disable — that
toggle exists only on the Automations screen.

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
   - **Watch non-ASCII punctuation in text strings.** `Nunito` only covers basic Latin/ASCII. Any non-ASCII character — including punctuation that *looks* harmless inside a sentence — renders as a **tofu square (□)** in a `Nunito` label. This applies to Python message/`StringProperty` strings too, not just KV. Common offenders: arrows `→ ← ↑ ↓`, em/en dashes `— –`, bullets `•`, check/cross `✓ ✗ ×`, degree `°`, ellipsis `…`, curly quotes `" " ' '`.
   - **Fix:** use plain ASCII (`->`, `-`, `*`, `x`, `deg`, `...`, straight quotes) for body text, OR set that label's `font_name: "ArialUnicode"` if you genuinely need the symbol, OR use a real `MaterialIcons` glyph (with `font_name: "MaterialIcons"`) when it's an icon.
6. **Background colors** — use `canvas.before` with `Color` + `Rectangle`, not widget `background_color`
7. **Text alignment** — `halign`/`valign` require `text_size: self.size` to take effect
   - **NEVER combine `text_size: self.size` with `width: self.texture_size[0]` on the same Label.** This is circular: the width depends on the texture, but the texture is constrained by `text_size` (the width). The width collapses to ~one character, so the text **wraps vertically (one letter per line) and runs off-screen** — this is the #1 cause of broken header/title bars.
   - **For a fixed-size label** (header titles, value readouts, toolbar labels): set an explicit `size_hint_x: None` + `width: dp(N)` AND `text_size: self.size`. This is the proven pattern in existing headers (e.g. `screens/DevTools/devtools.kv`: `width: dp(80)` + `text_size: self.size`).
   - **For a label that must hug its text width** (auto-size): use `size_hint_x: None` + `width: self.texture_size[0]` and **omit `text_size`** (do not set it). The label then sizes to the glyphs; `halign` is moot because the box already hugs the text.
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
| `surface_color` | `BACKGROUND_SURFACE` | Raised surface (cards, rows) |
| `border_color` | `BACKGROUND_BORDER` | Hairlines, dividers |
| `text_color` | `TEXT_PRIMARY` | Primary text |
| `muted_color` | `TEXT_SECONDARY` | Secondary/dimmed text |
| `accent_color` | `ACCENT_PRIMARY` | Accent highlights |
| `status_color` | `TEXT_SECONDARY` | Status indicators |

**Derived colors** (auto-calculated if the property exists on your class):
| Property | Derivation |
|----------|------------|
| `card_color` | `BACKGROUND_SURFACE` RGB at alpha 1.0 |
| `sidebar_color` | `BACKGROUND_SECONDARY` |
| `divider_color` | `BACKGROUND_BORDER` RGB at alpha 1.0 |
| `row_bg_color` | `BACKGROUND_SURFACE` RGB with 0.70 alpha |

Elevation uses the explicit `BACKGROUND_SURFACE`/`BACKGROUND_BORDER` tokens rather than
multiplying `header_color` — multiplying only elevates correctly on dark backgrounds, so
the old approach broke light mode.

`on_config_update()` also **cascades to every descendant** (`self.walk(restrict=True)`),
calling each widget's `on_config_update(config)` if it has one, else its `_apply_theme()`.
So a custom composite only has to define one of those hooks to be re-themed for free — see
`composites/Notifications/notificationcenter.py` or `composites/Weather/weatherwidget.py`.

Widgets you build dynamically and hand colors to at construction (list rows, chips) capture
those values and are *not* updated by the cascade unless they define a hook. The usual fix is
to rebuild them in your screen's `on_config_update` — see `_rebuild_rows()` in
`composites/Notifications/notificationcenter.py`.

**Theme the screen on first entry — don't rely on literal `ColorProperty` defaults.**
**`reload_all()` never runs at startup.** Screens *are* constructed eagerly
(`PihomeScreenManager.load_screens()` imports every module and instantiates every class at
boot), but nothing themes them afterwards: `reload_all()` is only called from
`reload_configuration()` on a settings change, and from the theme/settings/DevTools events —
all user-triggered. So a screen keeps whatever its `ColorProperty` defaults were until the
user changes a setting or the theme. If your `ColorProperty` defaults are hardcoded literals, the
screen paints those wrong colors on first open and only snaps to the real theme after some
*later* `reload_all()` fires (e.g. the user visits Settings and comes back). The fix is two
parts, both required:

1. **Derive the defaults from the theme** at class scope, so even the first frame is correct:
   ```python
   from theme.theme import Theme
   _th = Theme()
   bg_color     = ColorProperty(_th.get_color(_th.BACKGROUND_PRIMARY))
   accent_color = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))
   # ...one line per standard color
   ```
2. **Apply the theme in `on_enter`** before you build/render any widgets, so a freshly
   created screen themes itself immediately instead of waiting for a future `reload_all()`:
   ```python
   def on_enter(self, *args):
       super().on_enter(*args)
       super().on_config_update(CONFIG)   # applies theme colors to self + children
       self._render()                      # build widgets AFTER colors are correct
   ```
   (`from util.configuration import CONFIG`.) If you build child widgets dynamically and pass
   them `color=self.text_color` etc., they must be built *after* this call or they'll capture
   the stale default. **Calendar (`screens/Calendar/calendar.py`) is the reference** — see its
   class-scope defaults and its `on_enter`. `screens/Automations/automations.py` follows the
   same shape. (EmporiumPower does *not* implement this pattern; don't copy it for theming.)

**For custom colors beyond the standard set:**
```python
from theme.theme import Theme

def on_config_update(self, config):
    th = Theme()
    self.danger_color = th.get_color(th.ALERT_DANGER)
    self.success_color = th.get_color(th.ALERT_SUCCESS)
    super().on_config_update(config)
```

**Available theme tokens** (the full set — see `theme/theme.py`):
- Backgrounds: `BACKGROUND_PRIMARY`, `BACKGROUND_SECONDARY`, `BACKGROUND_SURFACE`, `BACKGROUND_BORDER`
- Colors: `COLOR_PRIMARY`, `COLOR_SECONDARY`
- Accent: `ACCENT_PRIMARY`
- Text: `TEXT_PRIMARY`, `TEXT_SECONDARY`, `TEXT_DANGER`, `TEXT_SUCCESS`
- Buttons: `BUTTON_PRIMARY`, `BUTTON_SECONDARY`, `BUTTON_DANGER`, `BUTTON_SUCCESS`,
  `BUTTON_PRIMARY_ACCENT`, `BUTTON_SECONDARY_ACCENT`, `BUTTON_PRIMARY_TEXT`, `BUTTON_SECONDARY_TEXT`
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
| `PiHomeSwitch` | `from components.Switch.switch import PiHomeSwitch` | Toggle switch. `PiHomeSwitch(size=(dp(46), dp(26)), on_change=cb)` — `on_change` is consumed by `__init__`, so it is safe as a kwarg (unlike `on_*` properties, gotcha #11) |
| `NumberStepper` | `from components.NumberStepper.numberstepper import NumberStepper` | Increment/decrement number input. `NumberStepper(on_change=cb, value=1, min_val=0, max_val=30, unit="d")` |
| `DatePicker` | `from components.DatePicker.datepicker import DatePicker` | Date selection widget |
| `Empty` | `from components.Empty.empty import Empty` | Empty-state placeholder: `Empty(icon="⊘", message="...", subtitle="...")`. Its icon Label uses `ArialUnicode`, so pass a Unicode symbol, **not** a MaterialIcons codepoint |
| `Msgbox` | `from components.Msgbox.msgbox import MSGBOX_FACTORY, MSGBOX_TYPES, MSGBOX_BUTTONS` | Modal dialog / confirm: `MSGBOX_FACTORY.show(title=..., message=..., type=MSGBOX_TYPES["WARNING"], buttons=MSGBOX_BUTTONS["YES_NO"], on_yes=cb)`. Themes itself on each show |
| `Slider` | `from components.Slider.haslider import HASlider` / `from components.Slider.slidecontrol import SlideControl` | Custom slider controls |

Verify an import before relying on this table — `components/VideoPlayer/` is currently empty
despite the directory existing.

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
2. **`super().on_config_update(config)` must be called LAST — inside your `on_config_update` override** — it applies theme colors, which should happen after your custom config logic. This is *not* in tension with calling it **early inside `on_enter`** (gotcha #13): there you are deliberately invoking the base class's theming pass up front, before any widgets are built.
3. **`super().on_enter()` and `super().on_pre_leave()` must be called** — they manage `is_open` state and screen tracking.
4. **Always stop threads in `on_pre_leave`** — failing to do so causes resource leaks and stale UI updates.
5. **Lambda variable capture** — use default args: `lambda dt, x=x: func(x)`, NOT `lambda dt: func(x)`.
6. **Boolean configs are strings** — check with `.strip().lower() in ("1", "true")`.
7. **Don't use `time.sleep()` in threads** — use `self._stop_event.wait(seconds)` for interruptible waits.
8. **`text_size: self.size`** is required in KV for `halign`/`valign` to work on Labels.
9. **MaterialIcons** Always make sure that icons are used correctly and fonts are not mixed. Attempting to reference a MaterialIcon from a label with a different font will not work. Also **verify the codepoint actually exists in the bundled font** before using it — a missing glyph renders as a tofu square (□). Check with:
   ```bash
   venv/bin/python -c "from fontTools.ttLib import TTFont; f=TTFont('theme/fonts/MaterialIcons-Regular.ttf'); g=f.getBestCmap().get(0xe3e7); print('present' if g else 'MISSING')"
   ```
   **Then verify what actually landed in the file.** Pasting a raw glyph character into a
   source file can silently write an *empty string* — the icon just never appears, with no
   error anywhere. Prefer the `""` escape form, and audit a whole directory with:
   ```bash
   venv/bin/python -c "
   import glob,re
   from fontTools.ttLib import TTFont
   cmap=TTFont('theme/fonts/MaterialIcons-Regular.ttf').getBestCmap()
   for p in glob.glob('screens/MyScreen/*.py')+glob.glob('screens/MyScreen/*.kv'):
       s=open(p,encoding='utf-8').read()
       for m in re.finditer(r'text: \"\"|glyph=\"\"', s): print('EMPTY icon string in',p)
       for ch in s:
           if 0xE000<=ord(ch)<=0xF8FF and not cmap.get(ord(ch)):
               print('MISSING glyph U+%04X in %s'%(ord(ch),p))"
   ```
10. **Disabled / full-screen widgets swallow touches** — Kivy's `Widget.on_touch_down` returns `True` (consuming the event) for any **`disabled`** widget the touch collides with. So a `disabled`, full-screen overlay (e.g. an empty/error-state `Label` left on top with default `size_hint: (1, 1)`) silently eats **every** touch beneath it — scrolling and taps appear completely dead even though the widgets below are fine. For hidden overlays, toggle `opacity` only (do **not** also set `disabled`), size the overlay to its content, or remove it from the tree when inactive. Remember the **last child of a `FloatLayout` is topmost**, so overlays sit above everything.
11. **Never pass an `on_*` custom-callback property in a widget's constructor** — Kivy's `EventDispatcher.__init__` treats **any** kwarg starting with `on_` as an *event binding* (`self.bind(on_x=...)`), NOT as setting a property value. So `MyRow(on_pressed=cb)` binds `cb` to the `on_pressed` property-change event and leaves `self.on_pressed == None` — your tap/select callback silently never fires. **Assign it after construction instead:** `row = MyRow(...); row.on_pressed = cb`. (This is why existing tappable rows like `Cocktail`'s `DrinkListItem` set `on_pressed` post-construction.) Tip: avoid naming a plain callback property `on_*` at all — but if you do, never set it via kwarg.
12. **Write persistent files to `cache/`, never the project root.** Any file a screen persists across launches — JSON state, response caches, **auth tokens / secrets** — goes in the shared `cache/` directory (relative to cwd, e.g. `_FILE = "cache/myscreen_state.json"`), matching `cocktail_cache.json`, `ha_favorites.json`, `favorite_events.json`. This directory is **gitignored** (`/cache/`), so writing secrets anywhere else (like next to `base.ini` in the root) risks committing them. Before searching for *where* to put a persistent file, grep existing screens (`grep -rn "cache/" --include="*.py"`) instead of assuming. Call `os.makedirs(os.path.dirname(path), exist_ok=True)` before writing so a fresh checkout works. (Small per-screen save files in the screen's own dir, like HexGame's `game_state.json`, also exist — but use `cache/` for caches, tokens, and shared/secret state.)
13. **Screens paint un-themed until the first settings change** — `reload_all()` is never called at startup (only from `reload_configuration()` and the theme/settings/DevTools events), so hardcoded literal `ColorProperty` defaults show until a *later* theme refresh (e.g. visiting Settings) fixes them. Derive defaults from `Theme()` and apply the theme in `on_enter` (build dynamic child widgets only after). See **Theme System → "Theme the screen on first entry"** for the full pattern.
14. **`PiTextInput` doesn't theme its own background — white-on-white in dark mode.** `PiTextInput._apply_theme()` sets only the text/cursor/hint colors; the app-wide `<PiTextInput>` rule strips the default 9-patch image, so the field falls back to a solid **white** `background_color`. Always set the background yourself: clear `background_normal`/`background_active` (`= ""`) and paint a theme-driven fill, e.g. `ti.background_color = list(self.text_color[:3]) + [0.10]` (a faint panel that works in both modes), matching `screens/Settings/settings.kv`. Add a little `padding` too.

---

## Verifying a Screen

Use `venv/bin/python` for every check — the system `python3` has no Kivy.

The Kivy GUI cannot run **truly headless** (SDL2 needs a real display + OpenGL; the `dummy`
video driver has no GL, and attempting it aborts with "Unable to get a Window"). But on a Mac
with a real display attached, a normal windowed run works fine, so a screen *can* be rendered
and screenshotted automatically.

**Without opening a window:**

- **Syntax:** `venv/bin/python -m py_compile screens/<Dir>/*.py`
- **Manifest:** validate it is parseable JSON.
- **KV parse + widget registration + imports:** `venv/bin/python -c "import screens.<Dir>.<file>; print('OK')"`.
  Catches KV syntax errors, bad sibling imports, and unregistered custom widgets.
- **Pure logic:** keep parsing/state/formatting in a Kivy-free module and unit-test it
  (`screens/BambuLab/bambustate.py` + `tests/test_core.py`, `screens/BluetoothConnect/protocol.py`,
  `screens/Calendar/calstore.py`, `util/rulestore.py`).

**Render smoke test** (catches layout errors, missing `ids`, bad row construction — things an
import check cannot):

```python
app.sm.current = "_myscreen"      # REQUIRED: nothing is drawn if the screen isn't current
Clock.schedule_once(lambda dt: self.screen.on_enter(), 0.3)
Clock.schedule_once(self._shot, 2.5)          # let layout settle before capturing
...
Window.screenshot(name="/tmp/shot.png")       # writes /tmp/shot0001.png (it appends a counter)
```

A **black screenshot means nothing was being drawn** — almost always a screen that was added
to the `ScreenManager` but never made `current`, not a capture problem. Also print
`widget.size`/`pos` for a few children: on a Retina Mac the window is 2x (1600x960 for the
800x480 layout), so `dp()` values appear doubled.

Leave real interaction testing (touch, rotary, hardware) to the user on the Pi.

---

## Reference: Existing Screens

Use these as examples when building new screens:

- **BambuLab** (`screens/BambuLab/`) — Full-featured: always-on service + MQTT, camera streaming, threading, multi-page stats, rotary encoder, property observers, rule store
- **Calendar** (`screens/Calendar/`) — **the theming reference** (theme-derived defaults + `on_enter`), service/pure-logic/screen split, headless tests
- **Automations** (`screens/Automations/`) — dynamic row list with tap/toggle/delete, Msgbox confirm, empty state, aggregating across services
- **TaskManagerScreen** (`screens/TaskManagerScreen/`) — persisted list with custom row widget + delete confirm
- **Home** (`screens/Home/`) — Animations, gestures, multiple widgets, wallpaper management
- **Spotify** (`screens/Spotify/`) — OAuth2 flow with a QR pairing panel, media playback controls
- **ShaderTest** (`screens/ShaderTest/`) — GLSL shader usage
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
| Modal / confirm dialog | `components/Msgbox/msgbox.py` |
| Event base class & factory | `events/pihomeevent.py` |
| Thread marshalling (`run_on_main_thread`) | `util/helpers.py` |
| Automation rule store | `util/rulestore.py` |
| Legacy rule-store adapters (AirPlay, HA) | `util/rule_adapters.py` |
| Screen service loader | `util/screen_services.py` |
| Screen dependency auto-install | `util/dependencies.py` |
| Main app | `main.py` |
| Persistent state / cache / token files | `cache/` (project root, gitignored) |
