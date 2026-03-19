"""NanoleafScreen — Control Nanoleaf Shapes panels individually.

Features
--------
- Visual layout matching the physical wall arrangement (tappable panels)
- HSV colour wheel for per-panel or all-panel colour control
- Brightness slider
- Rotary encoder toggles between brightness and hue adjustment
- Live state polling with user-interaction lock to avoid overwriting changes
- Pairing flow (hold power button → tap Pair)
- Effects / scenes list
- Dynamic multi-controller support (add controllers via Settings)
"""

import colorsys
import math
import threading
import time

from kivy.clock import Clock
from kivy.graphics import Color as GColor, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import (
    BooleanProperty, ColorProperty, DictProperty, ListProperty,
    NumericProperty, ObjectProperty, StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView

from interface.pihomescreen import PiHomeScreen
from screens.Nanoleaf.colorwheel import ColorWheel
from screens.Nanoleaf.nanoleaf_api import NanoleafAPI
from screens.Nanoleaf.nanoleaf_discovery import NanoleafDiscovery
from screens.Nanoleaf.panel_canvas import PanelCanvas
from util.configuration import CONFIG
from util.helpers import toast
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/Nanoleaf/nanoleaf.kv")

# How long after a user interaction before polling resumes writing to UI.
# Must be longer than the poll interval to survive at least one poll cycle.
_INTERACTION_LOCK_S = 12.0

# Maximum controller slots available in Settings
_MAX_CONTROLLERS = 4

# Accent — Nanoleaf green
_ACCENT = [0.0, 0.75, 0.45, 1.0]


class NanoleafScreen(PiHomeScreen):
    """Nanoleaf Shapes controller screen."""

    # ── Theme colours ─────────────────────────────────────────────────────────
    bg_color     = ColorProperty([0.10, 0.10, 0.12, 1])
    header_color = ColorProperty([0.14, 0.14, 0.16, 1])
    card_color   = ColorProperty([0.12, 0.12, 0.14, 0.85])
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([1, 1, 1, 0.45])
    accent_color = ColorProperty(list(_ACCENT))
    status_color = ColorProperty([0.45, 0.45, 0.45, 1])

    # ── Controller state ──────────────────────────────────────────────────────
    active_controller = NumericProperty(0)
    power_on = BooleanProperty(False)

    # ── Panel data ────────────────────────────────────────────────────────────
    panels = ListProperty([])
    panel_colors = DictProperty({})
    selected_panel = NumericProperty(-1)
    side_length = NumericProperty(150)

    # ── Colour / brightness ───────────────────────────────────────────────────
    current_hue = NumericProperty(0)
    current_sat = NumericProperty(100)
    current_brightness = NumericProperty(100)
    brightness_text = StringProperty("100%")

    # ── UI state ──────────────────────────────────────────────────────────────
    set_all_mode = BooleanProperty(False)
    rotary_mode = StringProperty("brightness")
    rotary_mode_text = StringProperty("KNOB: BRIGHTNESS")
    effect_text = StringProperty("")
    status_text = StringProperty("Not Connected")
    show_pair_btn = BooleanProperty(False)
    show_empty_state = BooleanProperty(True)

    # ──────────────────────────────────────────────────────────────────────────

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Dynamic controller lists — sized by how many have IPs configured
        self._controllers = []  # list of dicts: {ip, token, name, api}
        self._stop_event = threading.Event()
        self._thread = None
        self._last_interaction = 0.0
        self._effects_cache = {}      # {ctrl_idx: [effect_names]}
        self._color_send_scheduled = False
        self._brightness_send_scheduled = False
        self._tab_widgets = []        # references to dynamic tab BoxLayouts
        self._layout_fetched = set()  # controller indices whose layout we've fetched
        self._discovery = None        # NanoleafDiscovery instance
        self._discovery_modal = None
        self._wheel_active = False    # True while user is dragging the colour wheel
        self._hw_brightness = 100     # actual Nanoleaf global brightness from API
        self._load_config()

    # ── Configuration ─────────────────────────────────────────────────────────

    def _load_config(self):
        controllers = []
        for i in range(1, _MAX_CONTROLLERS + 1):
            ip = CONFIG.get("nanoleaf", f"ip_{i}", "").strip()
            token = CONFIG.get("nanoleaf", f"token_{i}", "").strip()
            name = CONFIG.get("nanoleaf", f"name_{i}", "").strip()
            if ip:  # only include slots that have an IP
                api = NanoleafAPI(ip, token) if token else None
                controllers.append({
                    "ip": ip, "token": token,
                    "name": name or f"Controller {i}",
                    "api": api, "slot": i,
                })
        self._controllers = controllers

        self._refresh = max(3, CONFIG.get_int("nanoleaf", "refresh_interval", 5))

        # Clamp active controller to valid range
        if self._controllers:
            self.active_controller = min(self.active_controller, len(self._controllers) - 1)
        else:
            self.active_controller = 0

        self.show_empty_state = len(self._controllers) == 0
        self._update_pair_btn()
        Clock.schedule_once(lambda dt: self._rebuild_tabs(), 0)

    def _active_api(self):
        """Return the NanoleafAPI for the active controller, or None."""
        if 0 <= self.active_controller < len(self._controllers):
            return self._controllers[self.active_controller].get("api")
        return None

    def _active_ctrl(self):
        """Return the active controller dict, or None."""
        if 0 <= self.active_controller < len(self._controllers):
            return self._controllers[self.active_controller]
        return None

    def _update_pair_btn(self):
        ctrl = self._active_ctrl()
        if ctrl:
            self.show_pair_btn = bool(ctrl["ip"]) and not bool(ctrl["token"])
        else:
            self.show_pair_btn = False

    def on_config_update(self, config):
        self._load_config()
        if self.is_open:
            self._stop_work()
            Clock.schedule_once(lambda dt: self._start_work(), 0.5)
        super().on_config_update(config)

    # ── Dynamic controller tabs ─────────────────────────────────────────────

    def _rebuild_tabs(self):
        """Populate the header tab bar based on configured controllers."""
        container = self.ids.get("ctrl_tabs")
        if container is None:
            return
        container.clear_widgets()
        self._tab_widgets = []

        # Only show tabs when there are 2+ controllers
        if len(self._controllers) < 2:
            return

        for i, ctrl in enumerate(self._controllers):
            tab = self._make_tab_widget(i, ctrl["name"])
            tab.bind(pos=self._update_tab_visuals, size=self._update_tab_visuals)
            container.add_widget(tab)
            self._tab_widgets.append(tab)

        self._update_tab_visuals()

    def _make_tab_widget(self, idx, name):
        box = BoxLayout(size_hint_x=None, width=dp(100))
        lbl = Label(
            text=name, font_name="Nunito", font_size=sp(10),
            halign="center", valign="middle", shorten=True,
            shorten_from="right",
        )
        lbl.text_size = (dp(96), None)
        box.add_widget(lbl)
        return box

    def _update_tab_visuals(self, *args):
        """Redraw tab backgrounds to highlight the active controller."""
        for i, tab in enumerate(self._tab_widgets):
            tab.canvas.before.clear()
            active = (i == self.active_controller)
            with tab.canvas.before:
                if active:
                    GColor(*self.accent_color)
                else:
                    GColor(*self.card_color)
                RoundedRectangle(size=tab.size, pos=tab.pos, radius=[dp(4)])
            lbl = tab.children[0]
            lbl.bold = active
            lbl.color = self.bg_color if active else self.muted_color

    def on_active_controller(self, inst, val):
        self._update_tab_visuals()
        self._update_pair_btn()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, *args):
        self._load_config()
        self._start_work()
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        self._stop_work()
        if self._discovery:
            self._discovery.stop()
            self._discovery = None
        if self._discovery_modal:
            self._discovery_modal.dismiss()
            self._discovery_modal = None
        return super().on_pre_leave(*args)

    def _start_work(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._layout_fetched.clear()
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="nanoleaf-poll",
        )
        self._thread.start()

    def _stop_work(self):
        self._stop_event.set()

    # ── Background worker ─────────────────────────────────────────────────────

    def _worker(self):
        """Poll active controller for state.  Skips UI updates during user interaction."""
        while not self._stop_event.is_set():
            idx = self.active_controller
            api = self._active_api()

            if api is None:
                ctrl = self._active_ctrl()
                msg = "Not Configured"
                if ctrl and ctrl["ip"] and not ctrl["token"]:
                    msg = "No Token — Tap Pair"
                Clock.schedule_once(lambda dt, m=msg: self._set_status(m), 0)
                self._stop_event.wait(self._refresh)
                continue

            try:
                state = api.get_state()
                lf = idx in self._layout_fetched

                # Try to read actual per-panel colours from the effect data.
                # This runs on every poll so colours stay in sync with the
                # physical lights (e.g. after someone changes them via the
                # Nanoleaf app or another integration).
                per_panel = {}
                try:
                    per_panel = api.get_panel_colors()
                except Exception:
                    pass

                Clock.schedule_once(lambda dt, s=state, i=idx, f=lf, pp=per_panel:
                                    self._apply_state(s, i, f, pp), 0)
                self._layout_fetched.add(idx)

                # Cache effects list on first successful fetch
                if idx not in self._effects_cache:
                    try:
                        effects = api.get_effects_list()
                        self._effects_cache[idx] = effects if isinstance(effects, list) else []
                    except Exception:
                        pass

            except Exception as e:
                PIHOME_LOGGER.error(f"Nanoleaf: poll error (ctrl {idx + 1}): {e}")
                Clock.schedule_once(lambda dt: self._set_status("Connection Error"), 0)

            self._stop_event.wait(self._refresh)

    def _apply_state(self, state, ctrl_idx, layout_already_fetched, per_panel=None):
        """Push polled state to UI properties (main thread)."""
        # Don't overwrite if user is actively interacting
        if ctrl_idx != self.active_controller:
            return

        locked = (time.monotonic() - self._last_interaction) < _INTERACTION_LOCK_S

        # Always update layout on first fetch (positions don't change)
        if not layout_already_fetched:
            layout = state.get("panelLayout", {}).get("layout", {})
            positions = layout.get("positionData", [])
            side = layout.get("sideLength", 0)
            if positions:
                # Log shape types and sample positions for debugging
                shapes = {}
                for p in positions:
                    st = p.get("shapeType", -1)
                    shapes[st] = shapes.get(st, 0) + 1
                PIHOME_LOGGER.info(f"Nanoleaf: panel shape types: {shapes}")
                # Log first few panels for layout debugging
                for p in positions[:3]:
                    PIHOME_LOGGER.info(
                        f"Nanoleaf: panel {p.get('panelId')} shape={p.get('shapeType')} "
                        f"x={p.get('x')} y={p.get('y')} o={p.get('o')}"
                    )

                if side <= 0:
                    side = self._estimate_side_length(positions)
                    PIHOME_LOGGER.info(f"Nanoleaf: sideLength was 0, estimated {side}")
                self.panels = positions
                self.side_length = side
                PIHOME_LOGGER.info(f"Nanoleaf: loaded {len(positions)} panels, sideLength={side}")

        # Power
        on_state = state.get("state", {}).get("on", {})
        self.power_on = on_state.get("value", False)

        # Always track the real hardware brightness for per-panel compensation
        br = state.get("state", {}).get("brightness", {})
        hw_bri = br.get("value", 100)
        self._hw_brightness = hw_bri

        if not locked:
            # Brightness — update slider to match hardware
            self.current_brightness = hw_bri
            self.brightness_text = f"{int(hw_bri)}%"

            # Hue / Sat — KV bindings push these to the wheel for display.
            # on_color_pick only fires from user touch, so no feedback loop.
            hue_data = state.get("state", {}).get("hue", {})
            sat_data = state.get("state", {}).get("sat", {})
            self.current_hue = hue_data.get("value", self.current_hue)
            self.current_sat = sat_data.get("value", self.current_sat)

            # Per-panel colours — merge API per-panel data with global HSV
            # so every panel gets a colour even when the API only returns a
            # subset (common: *Static* animData only has the last-written panel).
            self._update_panel_colors(state, per_panel)

        # Effect name
        current_fx = state.get("effects", {}).get("select", "")
        if current_fx and current_fx != "*Solid*" and current_fx != "*Dynamic*" and current_fx != "*Static*":
            self.effect_text = f"Effect: {current_fx}"
        else:
            self.effect_text = ""

        # Status
        self._set_status("Connected")
        self.status_color = list(_ACCENT)

    @staticmethod
    def _estimate_side_length(positions):
        """Estimate side length from panel positions when the API returns 0.

        Computes the minimum distance between any two panel centres, then
        derives the side length.  The conversion factor depends on the
        dominant shape type:
        - Triangles: min centroid distance ≈ sideLength × 2/√3
        - Hexagons:  min centroid distance ≈ sideLength × √3
        """
        import math
        skip = {1, 3, 12}  # controller shapes
        renderable = [p for p in positions if p.get("shapeType") not in skip]
        if len(renderable) < 2:
            return 100  # fallback

        min_dist = float("inf")
        for i in range(len(renderable)):
            for j in range(i + 1, len(renderable)):
                dx = renderable[i]["x"] - renderable[j]["x"]
                dy = renderable[i]["y"] - renderable[j]["y"]
                d = math.sqrt(dx * dx + dy * dy)
                if d > 0:
                    min_dist = min(min_dist, d)

        if min_dist == float("inf"):
            return 100

        # Determine dominant shape to pick the right conversion factor
        hex_shapes = {4, 7}
        tri_shapes = {0, 8, 9}
        n_hex = sum(1 for p in renderable if p.get("shapeType") in hex_shapes)
        n_tri = sum(1 for p in renderable if p.get("shapeType") in tri_shapes)

        if n_hex >= n_tri:
            # Hexagons: min centroid distance ≈ side * √3
            estimated = min_dist / math.sqrt(3)
        else:
            # Triangles: min centroid distance ≈ side * 2/√3
            estimated = min_dist * math.sqrt(3) / 2.0

        return max(10, estimated)

    def _update_panel_colors(self, state, per_panel=None):
        """Build a complete panel colour map.

        Priority (highest → lowest):
        1. ``per_panel`` — real colours read from the effect's animData
        2. Global HSV from the API state (solid/static mode only)
        3. Dim placeholder colour (when a named effect is running)

        The Nanoleaf ``write/request`` API often returns only a subset of
        panels (e.g. the last one written), so we fill in the gaps with
        the global HSV to ensure every panel has a colour.
        """
        skip_shapes = {1, 3, 12}
        current_fx = state.get("effects", {}).get("select", "")
        is_effect = current_fx and current_fx not in ("*Solid*", "*Static*")

        # Compute the global HSV fallback colour
        if not is_effect:
            hue = state.get("state", {}).get("hue", {}).get("value", 0)
            sat = state.get("state", {}).get("sat", {}).get("value", 100)
            bri = state.get("state", {}).get("brightness", {}).get("value", 100)
            r, g, b = colorsys.hsv_to_rgb(hue / 360.0, sat / 100.0, bri / 100.0)
            fallback_rgb = (int(r * 255), int(g * 255), int(b * 255))
        else:
            fallback_rgb = (56, 56, 64)  # dim placeholder

        if not per_panel:
            per_panel = {}

        colors = {}
        for p in self.panels:
            pid = p.get("panelId", 0)
            shape = p.get("shapeType", 8)
            if shape in skip_shapes:
                continue
            if pid in per_panel:
                colors[pid] = per_panel[pid]
            elif is_effect and pid in self.panel_colors:
                # Effect running — keep existing colour if we have one
                colors[pid] = self.panel_colors[pid]
            else:
                colors[pid] = fallback_rgb

        if colors:
            self.panel_colors = colors

    def _set_status(self, text):
        self.status_text = text
        if "Error" in text or "Not" in text:
            self.status_color = [0.85, 0.25, 0.25, 1]
        elif text == "Connected":
            self.status_color = list(_ACCENT)
        else:
            self.status_color = [0.45, 0.45, 0.45, 1]

    # ── Touch handling ───────────────────────────────────────────────────────
    #
    # Kivy's touch dispatch through nested RelativeLayouts (ScreenManager →
    # Screen → inner RelativeLayout) can silently drop touches due to
    # coordinate-transform issues.  To avoid this we handle PanelCanvas and
    # ColorWheel hits directly using `self.to_local()` — the same mechanism
    # that already works for all the sidebar buttons.  The Slider is left to
    # Kivy's standard dispatch via super().

    def _try_panel_touch(self, lx, ly):
        """Hit-test panels using NanoleafScreen-local coords (lx, ly)."""
        if self.show_empty_state:
            return False
        pc = self.ids.get("panel_canvas")
        if not pc or not pc._panel_verts:
            return False
        # PanelCanvas lives inside a RelativeLayout — its _panel_verts are
        # computed relative to (self.x=0, self.y=0) inside that RL.
        # Convert screen-local coords to RelativeLayout-local coords.
        rl = pc.parent
        if not rl or not rl.collide_point(lx, ly):
            return False
        pc_x = lx - rl.x
        pc_y = ly - rl.y
        for pid, verts in pc._panel_verts.items():
            if pc._point_in_polygon(pc_x, pc_y, verts):
                PIHOME_LOGGER.info(f"Nanoleaf: direct panel hit {pid}")
                self.selected_panel = pid
                self.on_panel_tapped(None, pid)
                return True
        return False

    def _wheel_hs_from_local(self, lx, ly):
        """Compute (hue, sat, hit) from NanoleafScreen-local coords."""
        wheel = self.ids.get("color_wheel")
        if not wheel or not wheel.collide_point(lx, ly):
            return 0, 0, False
        cx = wheel.x + wheel.width / 2.0
        cy = wheel.y + wheel.height / 2.0
        s = min(wheel.width, wheel.height)
        radius = s / 2.0
        dx = lx - cx
        dy = ly - cy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > radius:
            return 0, 0, False
        hue = (math.degrees(math.atan2(dy, dx)) + 360) % 360
        sat = min(100.0, (dist / radius) * 100.0)
        return hue, sat, True

    def on_touch_down(self, touch):
        lx, ly = self.to_local(*touch.pos)

        # ── 1. Panel hit-test ──
        if self._try_panel_touch(lx, ly):
            return True

        # ── 2. Colour wheel ──
        hue, sat, hit = self._wheel_hs_from_local(lx, ly)
        if hit:
            touch.grab(self)
            self._wheel_active = True
            self.on_color_pick(None, hue, sat)
            return True

        # ── 3. Kivy dispatch for Slider / standard widgets ──
        ret = super().on_touch_down(touch)
        if ret:
            return True

        # ── 4. Manual button checks (same coord space as above) ──
        # Controller tabs
        for i, tab in enumerate(self._tab_widgets):
            if tab.collide_point(lx, ly):
                if i != self.active_controller:
                    self._switch_controller(i)
                return True

        # Power button
        power = self.ids.get("power_btn")
        if power and power.collide_point(lx, ly):
            self._toggle_power()
            return True

        # Set All button
        sa = self.ids.get("set_all_btn")
        if sa and sa.collide_point(lx, ly):
            self.set_all_mode = not self.set_all_mode
            return True

        # Effects button
        fx = self.ids.get("effects_btn")
        if fx and fx.collide_point(lx, ly):
            self._show_effects_popup()
            return True

        # Pair button
        pair = self.ids.get("pair_btn")
        if self.show_pair_btn and pair and pair.collide_point(lx, ly):
            self._start_pairing()
            return True

        # Add controller — empty state button
        add_btn = self.ids.get("add_ctrl_btn")
        if self.show_empty_state and add_btn and add_btn.collide_point(lx, ly):
            self._show_discovery_modal()
            return True

        # Add controller — header "+" button
        add_hdr = self.ids.get("add_btn_header")
        if not self.show_empty_state and add_hdr and add_hdr.collide_point(lx, ly):
            self._show_discovery_modal()
            return True

        return False

    def on_touch_move(self, touch):
        if touch.grab_current is self and self._wheel_active:
            lx, ly = self.to_local(*touch.pos)
            hue, sat, hit = self._wheel_hs_from_local(lx, ly)
            if not hit:
                # Dragged outside wheel — clamp to edge
                wheel = self.ids.get("color_wheel")
                if wheel:
                    cx = wheel.x + wheel.width / 2.0
                    cy = wheel.y + wheel.height / 2.0
                    dx = lx - cx
                    dy = ly - cy
                    hue = (math.degrees(math.atan2(dy, dx)) + 360) % 360
                    sat = 100.0
                    hit = True
            if hit:
                self.on_color_pick(None, hue, sat)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self and self._wheel_active:
            touch.ungrab(self)
            self._wheel_active = False
            lx, ly = self.to_local(*touch.pos)
            hue, sat, hit = self._wheel_hs_from_local(lx, ly)
            if hit:
                self.on_color_pick(None, hue, sat)
            return True
        return super().on_touch_up(touch)

    # ── Controller switching ──────────────────────────────────────────────────

    def _switch_controller(self, idx):
        self.active_controller = idx
        self.panels = []
        self.panel_colors = {}
        self.selected_panel = -1
        self.effect_text = ""
        self._layout_fetched.discard(idx)  # force layout re-fetch for this controller
        self._update_pair_btn()

        ctrl = self._active_ctrl()
        if ctrl is None or ctrl["api"] is None:
            msg = "Not Configured"
            if ctrl and ctrl["ip"] and not ctrl["token"]:
                msg = "No Token — Tap Pair"
            self._set_status(msg)
        else:
            self._set_status("Switching...")

    # ── Panel tap ─────────────────────────────────────────────────────────────

    def on_panel_tapped(self, widget, panel_id):
        """Called when user taps a panel on the canvas."""
        PIHOME_LOGGER.info(f"Nanoleaf: panel tapped: {panel_id}")
        self.selected_panel = panel_id
        self._mark_interaction()

        # Read selected panel's current colour into the wheel.
        # Only update hue and saturation — keep the current brightness
        # unchanged so tapping a panel doesn't reset the slider.
        # The stored RGB already has brightness baked in, so we extract
        # H and S at V=1 by normalising the RGB values.
        rgb = self.panel_colors.get(panel_id)
        if rgb:
            h, s, v = colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
            self.current_hue = h * 360
            self.current_sat = s * 100

    # ── Colour changes ────────────────────────────────────────────────────────

    def on_color_pick(self, widget, hue, saturation):
        """Called when user touches/drags the colour wheel (on_color_pick event).

        This is dispatched directly from user touch — NOT from KV binding
        changes — so it always represents a real user action.
        """
        self.current_hue = hue
        self.current_sat = saturation
        self._mark_interaction()
        self._schedule_color_send()

    def on_brightness_slider(self, value):
        """Called when brightness slider moves."""
        self.current_brightness = value
        self.brightness_text = f"{int(value)}%"
        self._mark_interaction()
        self._schedule_brightness_send()

    def _schedule_color_send(self):
        """Throttle colour sends to avoid flooding the API."""
        if self._color_send_scheduled:
            return
        self._color_send_scheduled = True
        Clock.schedule_once(lambda dt: self._send_color(), 0.15)

    def _send_color(self):
        self._color_send_scheduled = False
        api = self._active_api()
        if api is None:
            PIHOME_LOGGER.info("Nanoleaf: _send_color skipped — no API")
            return

        # Compute RGB from our own properties
        r_f, g_f, b_f = colorsys.hsv_to_rgb(
            self.current_hue / 360.0,
            self.current_sat / 100.0,
            self.current_brightness / 100.0,
        )
        r, g, b = int(r_f * 255), int(g_f * 255), int(b_f * 255)
        PIHOME_LOGGER.info(
            f"Nanoleaf: _send_color rgb=({r},{g},{b}) "
            f"selected={self.selected_panel} set_all={self.set_all_mode}"
        )

        if self.selected_panel >= 0 and not self.set_all_mode:
            # Single panel mode — update local colour immediately
            pid = self.selected_panel
            colors = dict(self.panel_colors)
            colors[pid] = (r, g, b)
            self.panel_colors = colors
            # Send ALL panel colours so the *Static* animData always has
            # the full set — this lets future get_panel_colors() reads
            # return complete per-panel data instead of only the last panel.
            all_colors = {k: v for k, v in colors.items()}
            threading.Thread(
                target=self._do_set_panel_colors, args=(api, all_colors),
                daemon=True, name="nanoleaf-setpanel",
            ).start()
        else:
            # Set all mode (explicit toggle or no panel selected)
            threading.Thread(
                target=self._do_set_all_color, args=(api, r, g, b),
                daemon=True, name="nanoleaf-setall",
            ).start()
            # Update local panel colours immediately for visual feedback
            colors = {}
            for pid in self.panel_colors:
                colors[pid] = (r, g, b)
            self.panel_colors = colors

    @staticmethod
    def _do_set_panel_colors(api, panel_colors):
        """Send all panel colours in one shot so animData is complete."""
        try:
            api.set_panel_colors(panel_colors)
        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf: set panel colours error: {e}")

    @staticmethod
    def _do_set_all_color(api, r, g, b):
        try:
            api.set_all_color(r, g, b)
        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf: set all colour error: {e}")

    # ── Power toggle ──────────────────────────────────────────────────────────

    def _toggle_power(self):
        api = self._active_api()
        if api is None:
            toast("No controller configured", "warning", 2)
            return
        new_state = not self.power_on
        self.power_on = new_state
        self._mark_interaction()
        threading.Thread(
            target=self._do_set_power, args=(api, new_state),
            daemon=True, name="nanoleaf-power",
        ).start()

    @staticmethod
    def _do_set_power(api, on):
        try:
            api.set_power(on)
        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf: power toggle error: {e}")

    # ── Pairing ───────────────────────────────────────────────────────────────

    def _start_pairing(self):
        ctrl = self._active_ctrl()
        if ctrl is None or not ctrl["ip"]:
            toast("Set the controller IP in Settings first", "warning", 3)
            return
        toast("Hold the power button on your Nanoleaf for 5-7 seconds, then wait...", "info", 5)
        threading.Thread(
            target=self._do_pair, args=(self.active_controller, ctrl["ip"], ctrl["slot"]),
            daemon=True, name="nanoleaf-pair",
        ).start()

    def _do_pair(self, ctrl_idx, ip, slot):
        # Give the user time to press the button
        time.sleep(2)
        api = NanoleafAPI(ip)
        attempts = 0
        while attempts < 15 and not self._stop_event.is_set():
            try:
                token = api.pair()
                if token:
                    CONFIG.set("nanoleaf", f"token_{slot}", token)
                    Clock.schedule_once(lambda dt, t=token, i=ctrl_idx: self._on_paired(i, t), 0)
                    return
            except Exception:
                pass
            attempts += 1
            self._stop_event.wait(2)

        Clock.schedule_once(lambda dt: toast("Pairing failed — try again", "error", 3), 0)

    def _on_paired(self, ctrl_idx, token):
        if ctrl_idx < len(self._controllers):
            ctrl = self._controllers[ctrl_idx]
            ctrl["token"] = token
            ctrl["api"] = NanoleafAPI(ctrl["ip"], token)
        self._update_pair_btn()
        toast("Paired successfully!", "success", 3)

    # ── Controller discovery ────────────────────────────────────────────────

    def _show_discovery_modal(self):
        """Open a modal that scans for Nanoleaf devices on the network."""
        if not NanoleafDiscovery.is_available():
            toast("Install zeroconf: pip install zeroconf", "error", 3)
            self._show_manual_ip_modal()
            return

        modal = ModalView(
            size_hint=(0.65, 0.7),
            background_color=(0, 0, 0, 0),
            overlay_color=(0, 0, 0, 0.6),
        )
        self._discovery_modal = modal

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(8))
        root.canvas.before.clear()
        with root.canvas.before:
            GColor(*(self.header_color[:3] + [0.95]))
            RoundedRectangle(size=root.size, pos=root.pos, radius=[dp(10)])
        root.bind(size=lambda w, v: self._redraw_modal_bg(root),
                  pos=lambda w, v: self._redraw_modal_bg(root))

        # Title row
        title_row = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        title_row.add_widget(Label(
            text="\ue1ff", font_name="MaterialIcons", font_size=sp(20),
            color=self.accent_color, size_hint_x=None, width=dp(28),
        ))
        title_row.add_widget(Label(
            text="Discover Controllers", font_name="Nunito",
            font_size=sp(14), bold=True, color=self.text_color,
            halign="left", valign="middle",
        ))
        root.add_widget(title_row)

        # Scanning status label
        scan_label = Label(
            text="Scanning your network...", font_name="Nunito",
            font_size=sp(11), color=self.muted_color,
            size_hint_y=None, height=dp(22),
            halign="center", valign="middle",
        )
        scan_label.text_size = (None, dp(22))
        root.add_widget(scan_label)

        # Device list (scrollable)
        sv = ScrollView(do_scroll_x=False, bar_width=dp(3))
        device_list = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(4),
        )
        device_list.bind(minimum_height=device_list.setter("height"))
        sv.add_widget(device_list)
        root.add_widget(sv)

        # Manual IP button at bottom
        manual_row = BoxLayout(size_hint_y=None, height=dp(36))
        manual_lbl = Label(
            text="Enter IP address manually", font_name="Nunito",
            font_size=sp(10), color=self.accent_color,
            halign="center", valign="middle",
        )
        manual_lbl.text_size = (None, dp(36))
        manual_row.add_widget(manual_lbl)
        root.add_widget(manual_row)

        modal.add_widget(root)
        modal.open()

        # Store references for callbacks
        self._disc_device_list = device_list
        self._disc_scan_label = scan_label
        self._disc_manual_row = manual_row
        self._disc_found_ips = set()

        # Bind manual IP tap
        manual_row.bind(on_touch_down=lambda w, t: self._on_manual_ip_tap(w, t, modal))

        # Start mDNS scan
        self._discovery = NanoleafDiscovery(
            on_found=lambda dev: Clock.schedule_once(lambda dt, d=dev: self._on_device_found(d), 0),
            on_complete=lambda devs: Clock.schedule_once(lambda dt, ds=devs: self._on_scan_complete(ds), 0),
        )
        self._discovery.start()

    def _redraw_modal_bg(self, root):
        root.canvas.before.clear()
        with root.canvas.before:
            GColor(*(self.header_color[:3] + [0.95]))
            RoundedRectangle(size=root.size, pos=root.pos, radius=[dp(10)])

    def _on_device_found(self, device):
        """Called on main thread when a Nanoleaf is discovered."""
        if device["ip"] in self._disc_found_ips:
            return
        self._disc_found_ips.add(device["ip"])

        # Check if this device is already configured
        existing_ips = {c["ip"] for c in self._controllers}
        already_added = device["ip"] in existing_ips

        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8), padding=(dp(8), 0))
        row.canvas.before.clear()
        with row.canvas.before:
            GColor(*(self.card_color[:3] + [0.9]))
            RoundedRectangle(size=row.size, pos=row.pos, radius=[dp(6)])
        row.bind(
            size=lambda w, v: self._redraw_row_bg(w),
            pos=lambda w, v: self._redraw_row_bg(w),
        )

        # Info column
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        name_text = device.get("name", "Nanoleaf")
        if device.get("model"):
            name_text = f"{device['name']}  ({device['model']})"
        name_lbl = Label(
            text=name_text, font_name="Nunito", font_size=sp(11),
            bold=True, color=self.text_color,
            halign="left", valign="bottom",
        )
        name_lbl.bind(size=lambda w, v: setattr(w, 'text_size', w.size))
        info.add_widget(name_lbl)

        ip_lbl = Label(
            text=device["ip"], font_name="Nunito", font_size=sp(9),
            color=self.muted_color, halign="left", valign="top",
        )
        ip_lbl.bind(size=lambda w, v: setattr(w, 'text_size', w.size))
        info.add_widget(ip_lbl)
        row.add_widget(info)

        # Action label
        if already_added:
            action = Label(
                text="Added", font_name="Nunito", font_size=sp(10),
                color=self.muted_color, size_hint_x=None, width=dp(60),
                halign="center", valign="middle",
            )
        else:
            action = Label(
                text="ADD", font_name="Nunito", font_size=sp(10),
                bold=True, color=self.accent_color,
                size_hint_x=None, width=dp(60),
                halign="center", valign="middle",
            )
            row.bind(on_touch_down=lambda w, t, d=device:
                     self._on_discovery_device_tap(w, t, d))
        row.add_widget(action)

        self._disc_device_list.add_widget(row)
        self._disc_scan_label.text = f"Found {len(self._disc_found_ips)} controller(s)..."

    def _redraw_row_bg(self, widget):
        widget.canvas.before.clear()
        with widget.canvas.before:
            GColor(*(self.card_color[:3] + [0.9]))
            RoundedRectangle(size=widget.size, pos=widget.pos, radius=[dp(6)])

    def _on_scan_complete(self, devices):
        """Called when the mDNS scan finishes."""
        if hasattr(self, '_disc_scan_label') and self._disc_scan_label:
            n = len(devices)
            if n == 0:
                self._disc_scan_label.text = "No controllers found — try manual entry below"
            else:
                self._disc_scan_label.text = f"Found {n} controller(s)"

    def _on_discovery_device_tap(self, widget, touch, device):
        """User tapped a discovered device to add it."""
        if not widget.collide_point(*touch.pos):
            return False

        # Find the next available slot
        slot = self._next_available_slot()
        if slot is None:
            toast("Maximum 4 controllers — remove one in Settings first", "warning", 3)
            return True

        ip = device["ip"]
        name = device.get("name", f"Controller {slot}")

        # Save IP and name to config
        CONFIG.set("nanoleaf", f"ip_{slot}", ip)
        CONFIG.set("nanoleaf", f"name_{slot}", name)

        # Dismiss modal
        if self._discovery_modal:
            self._discovery_modal.dismiss()
            self._discovery_modal = None
        if self._discovery:
            self._discovery.stop()
            self._discovery = None

        # Reload config to pick up the new controller
        self._load_config()
        if self.is_open:
            self._stop_work()
            Clock.schedule_once(lambda dt: self._start_work(), 0.3)

        # Auto-start pairing for the newly added controller
        new_idx = None
        for i, ctrl in enumerate(self._controllers):
            if ctrl["ip"] == ip:
                new_idx = i
                break
        if new_idx is not None:
            self.active_controller = new_idx
            toast("Hold the power button on your Nanoleaf for 5-7 seconds...", "info", 5)
            ctrl = self._controllers[new_idx]
            threading.Thread(
                target=self._do_pair, args=(new_idx, ip, ctrl["slot"]),
                daemon=True, name="nanoleaf-pair",
            ).start()
        return True

    def _on_manual_ip_tap(self, widget, touch, modal):
        """User tapped 'Enter IP manually'."""
        if not widget.collide_point(*touch.pos):
            return False
        modal.dismiss()
        if self._discovery:
            self._discovery.stop()
            self._discovery = None
        self._show_manual_ip_modal()
        return True

    def _show_manual_ip_modal(self):
        """Show a simple modal with a text input for manual IP entry."""
        from components.Keyboard.keyboard import PiTextInput

        modal = ModalView(
            size_hint=(0.55, 0.35),
            background_color=(0, 0, 0, 0),
            overlay_color=(0, 0, 0, 0.6),
        )

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        with root.canvas.before:
            GColor(*(self.header_color[:3] + [0.95]))
            RoundedRectangle(size=root.size, pos=root.pos, radius=[dp(10)])
        root.bind(size=lambda w, v: self._redraw_modal_bg(root),
                  pos=lambda w, v: self._redraw_modal_bg(root))

        root.add_widget(Label(
            text="Enter Controller IP", font_name="Nunito",
            font_size=sp(14), bold=True, color=self.text_color,
            size_hint_y=None, height=dp(28),
        ))

        ip_input = PiTextInput(
            hint_text="192.168.1.50",
            font_size=sp(14),
            size_hint_y=None, height=dp(40),
            multiline=False,
        )
        root.add_widget(ip_input)

        btn_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))

        cancel_box = BoxLayout()
        with cancel_box.canvas.before:
            GColor(0.3, 0.3, 0.3, 1)
            RoundedRectangle(size=cancel_box.size, pos=cancel_box.pos, radius=[dp(4)])
        cancel_box.bind(size=lambda w, v: self._redraw_btn_bg(w, [0.3, 0.3, 0.3, 1]),
                        pos=lambda w, v: self._redraw_btn_bg(w, [0.3, 0.3, 0.3, 1]))
        cancel_lbl = Label(text="Cancel", font_name="Nunito", font_size=sp(11),
                           bold=True, color=self.text_color)
        cancel_box.add_widget(cancel_lbl)
        cancel_box.bind(on_touch_down=lambda w, t: modal.dismiss() if w.collide_point(*t.pos) else None)
        btn_row.add_widget(cancel_box)

        add_box = BoxLayout()
        with add_box.canvas.before:
            GColor(*self.accent_color)
            RoundedRectangle(size=add_box.size, pos=add_box.pos, radius=[dp(4)])
        add_box.bind(size=lambda w, v: self._redraw_btn_bg(w, self.accent_color),
                     pos=lambda w, v: self._redraw_btn_bg(w, self.accent_color))
        add_lbl = Label(text="Add & Pair", font_name="Nunito", font_size=sp(11),
                        bold=True, color=[1, 1, 1, 1])
        add_box.add_widget(add_lbl)
        add_box.bind(on_touch_down=lambda w, t, inp=ip_input, m=modal:
                     self._on_manual_ip_submit(w, t, inp, m))
        btn_row.add_widget(add_box)

        root.add_widget(btn_row)
        modal.add_widget(root)
        modal.open()

    def _redraw_btn_bg(self, widget, color):
        widget.canvas.before.clear()
        with widget.canvas.before:
            GColor(*color)
            RoundedRectangle(size=widget.size, pos=widget.pos, radius=[dp(4)])

    def _on_manual_ip_submit(self, widget, touch, ip_input, modal):
        if not widget.collide_point(*touch.pos):
            return False
        ip = ip_input.text.strip()
        if not ip:
            toast("Enter an IP address", "warning", 2)
            return True

        slot = self._next_available_slot()
        if slot is None:
            toast("Maximum 4 controllers — remove one in Settings first", "warning", 3)
            return True

        CONFIG.set("nanoleaf", f"ip_{slot}", ip)
        CONFIG.set("nanoleaf", f"name_{slot}", f"Controller {slot}")
        modal.dismiss()

        self._load_config()
        if self.is_open:
            self._stop_work()
            Clock.schedule_once(lambda dt: self._start_work(), 0.3)

        # Find and switch to the new controller, start pairing
        for i, ctrl in enumerate(self._controllers):
            if ctrl["ip"] == ip:
                self.active_controller = i
                toast("Hold the power button on your Nanoleaf for 5-7 seconds...", "info", 5)
                threading.Thread(
                    target=self._do_pair, args=(i, ip, ctrl["slot"]),
                    daemon=True, name="nanoleaf-pair",
                ).start()
                break
        return True

    def _next_available_slot(self):
        """Find the next unused config slot (1-4), or None if all full."""
        used_slots = {c["slot"] for c in self._controllers}
        for s in range(1, _MAX_CONTROLLERS + 1):
            if s not in used_slots:
                return s
        return None

    # ── Effects popup ─────────────────────────────────────────────────────────

    def _show_effects_popup(self):
        idx = self.active_controller
        effects = self._effects_cache.get(idx, [])
        if not effects:
            api = self._active_api()
            if api:
                threading.Thread(
                    target=self._fetch_and_show_effects, args=(api, idx),
                    daemon=True, name="nanoleaf-fx",
                ).start()
            else:
                toast("No controller connected", "warning", 2)
            return
        self._build_effects_modal(effects)

    def _fetch_and_show_effects(self, api, idx):
        try:
            effects = api.get_effects_list()
            if isinstance(effects, list):
                self._effects_cache[idx] = effects
                Clock.schedule_once(lambda dt, e=effects: self._build_effects_modal(e), 0)
            else:
                Clock.schedule_once(lambda dt: toast("No effects found", "info", 2), 0)
        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf: effects fetch error: {e}")
            Clock.schedule_once(lambda dt: toast("Failed to load effects", "error", 2), 0)

    def _build_effects_modal(self, effects):
        modal = ModalView(
            size_hint=(0.5, 0.75),
            background_color=(0, 0, 0, 0.85),
            overlay_color=(0, 0, 0, 0.5),
        )

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))

        # Title
        title = Label(
            text="Effects", font_name="Nunito", font_size=sp(14),
            bold=True, color=self.text_color,
            size_hint_y=None, height=dp(30),
        )
        root.add_widget(title)

        # Scrollable list
        sv = ScrollView(do_scroll_x=False, bar_width=dp(3))
        content = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(4),
        )
        content.bind(minimum_height=content.setter("height"))

        for name in sorted(effects):
            btn = Label(
                text=name, font_name="Nunito", font_size=sp(12),
                color=self.text_color, size_hint_y=None, height=dp(36),
                halign="left", valign="middle",
            )
            btn.text_size = (None, dp(36))
            btn.bind(
                on_touch_down=lambda inst, touch, n=name, m=modal:
                    self._on_effect_tap(inst, touch, n, m)
            )
            content.add_widget(btn)

        sv.add_widget(content)
        root.add_widget(sv)
        modal.add_widget(root)
        modal.open()

    def _on_effect_tap(self, inst, touch, name, modal):
        if not inst.collide_point(*touch.pos):
            return False
        modal.dismiss()
        self.effect_text = f"Effect: {name}"
        self._mark_interaction()
        api = self._active_api()
        if api:
            threading.Thread(
                target=self._do_set_effect, args=(api, name),
                daemon=True, name="nanoleaf-fx-set",
            ).start()
        return True

    @staticmethod
    def _do_set_effect(api, name):
        try:
            api.set_effect(name)
        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf: set effect error: {e}")

    # ── Rotary encoder ────────────────────────────────────────────────────────

    def on_rotary_turn(self, direction, button_pressed):
        self._mark_interaction()
        if self.rotary_mode == "brightness":
            new_val = max(1, min(100, self.current_brightness + direction * 5))
            self.current_brightness = new_val
            self.brightness_text = f"{int(new_val)}%"
            self._schedule_brightness_send()
        else:
            new_hue = (self.current_hue + direction * 10) % 360
            self.current_hue = new_hue
            self._schedule_color_send()
        return True

    def on_rotary_pressed(self):
        if self.rotary_mode == "brightness":
            self.rotary_mode = "hue"
            self.rotary_mode_text = "KNOB: HUE"
        else:
            self.rotary_mode = "brightness"
            self.rotary_mode_text = "KNOB: BRIGHTNESS"
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True

    def _schedule_brightness_send(self):
        """Send brightness to controller (throttled)."""
        if self._brightness_send_scheduled:
            return
        self._brightness_send_scheduled = True
        Clock.schedule_once(lambda dt: self._send_brightness(), 0.15)

    def _send_brightness(self):
        self._brightness_send_scheduled = False
        api = self._active_api()
        if api is None:
            return

        if self.selected_panel >= 0 and not self.set_all_mode:
            # Per-panel brightness: bake the desired brightness into the
            # selected panel's RGB via _send_color().  Also set global
            # brightness to 100% so the full RGB range is available on
            # the hardware (the Nanoleaf multiplies per-panel RGB by
            # global brightness, so anything < 100% caps our range).
            PIHOME_LOGGER.info(
                f"Nanoleaf: _send_brightness per-panel val={int(self.current_brightness)}"
            )
            self._hw_brightness = 100
            threading.Thread(
                target=self._do_set_brightness, args=(api, 100),
                daemon=True, name="nanoleaf-bri-global",
            ).start()
            self._send_color()
        else:
            # SET ALL / no panel selected: global brightness endpoint
            val = int(self.current_brightness)
            PIHOME_LOGGER.info(f"Nanoleaf: _send_brightness global val={val}")
            threading.Thread(
                target=self._do_set_brightness, args=(api, val),
                daemon=True, name="nanoleaf-bri",
            ).start()

    @staticmethod
    def _do_set_brightness(api, value):
        try:
            api.set_brightness(value)
        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf: brightness error: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mark_interaction(self):
        """Record that the user just interacted — suppresses poll overwrite."""
        self._last_interaction = time.monotonic()

    def on_current_brightness(self, inst, val):
        self.brightness_text = f"{int(val)}%"
