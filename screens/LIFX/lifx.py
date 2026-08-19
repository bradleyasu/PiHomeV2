"""LIFX screen - rooms and bulbs on the left, controls for the selection on the right.

All network work belongs to ``LIFX_SERVICE``; this module only renders its
snapshots and sends intent back.  Three guards keep the poll loop from fighting
the user's finger:

``_programmatic``  set while *we* write a widget's value, so its handler no-ops
``_locked_until``  a short window after a touch where snapshots don't overwrite
                   the panel's colour/brightness properties
throttle/debounce  wheel and kelvin drags send on a 150ms leading throttle, the
                   brightness slider on a 400ms trailing debounce

The service applies the same idea per bulb (see its ``_optimistic``), which is
what keeps a room row and the control panel from ever disagreeing.
"""

import time

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from components.ColorWheel.colorwheel import ColorWheel
from components.KelvinSlider.kelvinslider import KelvinSlider
from components.Keyboard.keyboard import PiTextInput
from components.Msgbox.msgbox import MSGBOX_BUTTONS, MSGBOX_FACTORY, MSGBOX_TYPES
from components.Slider.haslider import HASlider          # noqa: F401 (KV needs it)
from components.Switch.switch import PiHomeSwitch
from interface.pihomescreen import PiHomeScreen
from screens.LIFX import protocol as p
from screens.LIFX.bulbrow import (          # noqa: F401 (KV needs these registered)
    ICON_PALETTE,
    ICON_STYLE,
    ICON_SUN,
    BulbRow,
    IconButton,
    KelvinChip,
    ModeTab,
    RoomHeaderRow,
    SceneCard,
    SwatchButton,
)
from screens.LIFX.scenes import scene_swatches
from screens.LIFX.services.lifx_service import LIFX_SERVICE
from theme.theme import Theme
from util.configuration import CONFIG
from util.helpers import toast
from util.phlog import PIHOME_LOGGER

_th = Theme()

_BUILD_CHUNK = 6          # rows added per frame, so opening never hitches
_INTERACTION_LOCK = 2.5   # seconds a touch outranks incoming snapshots
_COLOR_THROTTLE = 0.15    # leading-edge send rate while dragging
_BRI_DEBOUNCE = 0.4       # trailing send after the slider settles

MODE_COLOR = "color"
MODE_WHITE = "white"
MODE_SCENES = "scenes"

_PRESETS = [
    ("Red", 0, 100), ("Orange", 30, 100), ("Gold", 45, 85), ("Green", 120, 100),
    ("Cyan", 180, 100), ("Blue", 220, 100), ("Purple", 280, 100), ("Pink", 320, 70),
]

_KELVIN_PRESETS = [
    ("CANDLE", 1500), ("WARM", 2700), ("SOFT", 3000),
    ("NEUTRAL", 4000), ("COOL", 5000), ("DAY", 6500),
]


class LifxEmptyState(BoxLayout):
    """Shown in place of the split view when there is nothing to control."""

    title_text = StringProperty("No LIFX bulbs found")
    subtitle_text = StringProperty("")
    text_color = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))

    def _apply_theme(self, *args):
        theme = Theme()
        self.text_color = theme.get_color(theme.TEXT_PRIMARY)
        self.muted_color = theme.get_color(theme.TEXT_SECONDARY)


Builder.load_file("./screens/LIFX/lifx.kv")


class LIFXScreen(PiHomeScreen):
    """Discover, group and control LIFX bulbs over the LAN."""

    # Standard theme names, so PiHomeScreen.on_config_update repaints them.
    # Defaults come from the theme, not literals: screens are built at boot but
    # never themed until some later reload_all(), so a literal would paint the
    # wrong colour on first open.
    bg_color = ColorProperty(_th.get_color(_th.BACKGROUND_PRIMARY))
    header_color = ColorProperty(_th.get_color(_th.BACKGROUND_SECONDARY))
    surface_color = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    border_color = ColorProperty(_th.get_color(_th.BACKGROUND_BORDER))
    text_color = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    accent_color = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))
    status_color = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    card_color = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    row_bg_color = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    divider_color = ColorProperty(_th.get_color(_th.BACKGROUND_BORDER))
    sidebar_color = ColorProperty(_th.get_color(_th.BACKGROUND_SECONDARY))

    mode = StringProperty(MODE_COLOR)
    sel_title = StringProperty("All Lights")
    sel_subtitle = StringProperty("")
    bri_text = StringProperty("0%")
    status_text = StringProperty("")
    footer_text = StringProperty("")
    supports_color = BooleanProperty(True)

    cur_hue = NumericProperty(0.0)
    cur_sat = NumericProperty(0.0)
    cur_bri = NumericProperty(0.0)
    cur_kelvin = NumericProperty(3500)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._sel_kind = "all"
        self._sel_key = None
        self._sel_serials = []

        self._programmatic = False
        self._locked_until = 0.0
        self._color_send_scheduled = False
        self._bri_debounce = None

        self._rows = {}            # serial or ("room", name) -> widget
        self._row_signature = None
        self._build_token = 0
        self._build_queue = []

        self._panels = {}
        self._tabs = {}
        self._master_switch = None
        self._scene_signature = None
        self._snapshot = None
        self._content = None
        self._empty = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def on_enter(self, *args):
        super().on_enter(*args)
        CONFIG.reload()
        # Theme before building anything: widgets created below capture these
        # colours at construction and would otherwise keep stale ones.
        super().on_config_update(CONFIG)

        self._content = self.ids.content
        LIFX_SERVICE.set_fast_poll(True)
        LIFX_SERVICE.add_listener(self._on_snapshot)
        self._build_tabs()
        self._on_snapshot(LIFX_SERVICE.get_snapshot())

    def on_pre_leave(self, *args):
        LIFX_SERVICE.set_fast_poll(False)
        LIFX_SERVICE.remove_listener(self._on_snapshot)
        if self._bri_debounce is not None:
            self._bri_debounce.cancel()
            self._bri_debounce = None
        self._build_queue = []
        return super().on_pre_leave(*args)

    def on_config_update(self, config):
        LIFX_SERVICE.reload()
        super().on_config_update(config)
        if self.is_open:
            # Rows and panels take their colours at construction, so a theme
            # change means rebuilding them.
            self._panels = {}
            self._row_signature = None
            self._build_tabs()
            if self._snapshot is not None:
                self._on_snapshot(self._snapshot)

    # ── Snapshots ─────────────────────────────────────────────────────────

    def _on_snapshot(self, snapshot):
        """Main thread: the service marshals this through Clock."""
        self._snapshot = snapshot
        self._update_status(snapshot)

        rooms = snapshot["rooms"]
        if not snapshot["bulbs"]:
            self._show_empty(snapshot)
            return
        self._show_content()

        signature = self._signature(rooms)
        if signature != self._row_signature:
            self._row_signature = signature
            self._rebuild_rows(rooms, snapshot)
        else:
            self._sync_rows(snapshot)

        self._resolve_selection(snapshot)
        self._refresh_panel(snapshot)

    @staticmethod
    def _signature(rooms):
        """Structure only - state changes must not trigger a rebuild."""
        return tuple((room["name"], tuple(room["serials"])) for room in rooms)

    def _update_status(self, snapshot):
        if not snapshot["enabled"]:
            self.status_text = "Disabled in Settings"
            self.status_color = Theme().get_color(Theme().TEXT_SECONDARY)
        elif snapshot["scanning"]:
            self.status_text = "Scanning..."
            self.status_color = Theme().get_color(Theme().ALERT_WARNING)
        elif snapshot["error"]:
            self.status_text = str(snapshot["error"])[:60]
            self.status_color = Theme().get_color(Theme().ALERT_DANGER)
        else:
            online = sum(1 for e in snapshot["bulbs"].values()
                         if e.get("online", True))
            self.status_text = ""
            self.status_color = (Theme().get_color(Theme().ALERT_SUCCESS) if online
                                 else Theme().get_color(Theme().TEXT_SECONDARY))

        bulbs = len(snapshot["bulbs"])
        rooms = len(snapshot["rooms"])
        self.footer_text = "{} light{} in {} room{}".format(
            bulbs, "" if bulbs == 1 else "s", rooms, "" if rooms == 1 else "s")

    # ── Empty state ───────────────────────────────────────────────────────

    def _show_empty(self, snapshot):
        if self._empty is None:
            self._empty = LifxEmptyState()
        if snapshot["enabled"]:
            self._empty.title_text = "No LIFX bulbs found"
            self._empty.subtitle_text = (
                "Make sure your bulbs are powered on and on this network, "
                "then tap the refresh icon.")
        else:
            self._empty.title_text = "LIFX is turned off"
            self._empty.subtitle_text = "Enable it in Settings to discover bulbs."
        self._empty._apply_theme()

        body = self.ids.body
        if self._empty.parent is None:
            body.clear_widgets()
            body.add_widget(self._empty)

    def _show_content(self):
        body = self.ids.body
        if self._content.parent is None:
            body.clear_widgets()
            body.add_widget(self._content)

    # ── Row list ──────────────────────────────────────────────────────────

    def _rebuild_rows(self, rooms, snapshot):
        self.ids.rows_box.clear_widgets()
        self._rows = {}
        self._build_token += 1
        token = self._build_token

        queue = [("all", None, None)]
        for room in rooms:
            queue.append(("room", room, None))
            for serial in room["serials"]:
                queue.append(("bulb", room, serial))
        self._build_queue = queue

        self._drain_build_queue(token, snapshot)

    def _drain_build_queue(self, token, snapshot):
        """Stream rows in over several frames so the screen slides in smoothly."""
        if token != self._build_token:
            return
        box = self.ids.rows_box
        for _ in range(_BUILD_CHUNK):
            if not self._build_queue:
                self._sync_rows(snapshot)
                return
            kind, room, serial = self._build_queue.pop(0)
            if kind == "all":
                box.add_widget(self._make_room_row(None))
            elif kind == "room":
                box.add_widget(self._make_room_row(room))
            else:
                box.add_widget(self._make_bulb_row(serial, snapshot))
        Clock.schedule_once(
            lambda dt: self._drain_build_queue(token, snapshot), 0)

    def _make_room_row(self, room):
        name = "All Lights" if room is None else room["name"]
        key = ("room", None if room is None else room["name"])

        row = RoomHeaderRow()
        row.room = name
        row._apply_theme()
        # Assigned after construction: an on_* constructor kwarg would be bound
        # as an event and the callback would silently never fire.
        row.select_cb = (self.select_all if room is None
                         else (lambda n=room["name"]: self.select_room(n)))

        switch = PiHomeSwitch(size=(dp(40), dp(22)))
        switch.on_change = lambda value, r=room: self._on_room_switch(r, value)
        row.attach_switch(switch)
        row.switch = switch

        self._rows[key] = row
        return row

    def _make_bulb_row(self, serial, snapshot):
        row = BulbRow()
        row.serial = serial
        row._apply_theme()
        row.select_cb = lambda s=serial: self.select_bulb(s)

        switch = PiHomeSwitch(size=(dp(38), dp(21)))
        switch.on_change = lambda value, s=serial: self._on_bulb_switch(s, value)
        row.attach_switch(switch)
        row.switch = switch

        self._rows[serial] = row
        return row

    def _sync_rows(self, snapshot):
        """Push state into the rows that already exist - no rebuild, no flicker."""
        bulbs = snapshot["bulbs"]
        self._programmatic = True
        try:
            for room in snapshot["rooms"]:
                row = self._rows.get(("room", room["name"]))
                if row is None:
                    continue
                row.subtitle = "{} on".format(room["on_count"])
                row.selected = (self._sel_kind == "group"
                                and self._sel_key == room["name"])
                row.switch.set_state(room["any_on"], animate=False)

            row = self._rows.get(("room", None))
            if row is not None:
                any_on = any(e.get("power") for e in bulbs.values())
                row.subtitle = "{} on".format(
                    sum(1 for e in bulbs.values() if e.get("power")))
                row.selected = self._sel_kind == "all"
                row.switch.set_state(any_on, animate=False)

            for serial, entry in bulbs.items():
                row = self._rows.get(serial)
                if row is None:
                    continue
                row.label = entry.get("label") or serial
                row.is_on = bool(entry.get("power"))
                row.online = bool(entry.get("online", True))
                row.selected = (self._sel_kind == "bulb"
                                and self._sel_key == serial)
                level = (entry.get("brightness", 0) or 0) / float(p.U16) * 100.0
                row.level = "{}%".format(int(round(level))) if row.is_on else "--"
                rgb = p.hsbk_to_rgb(entry.get("hue", 0), entry.get("saturation", 0),
                                    p.U16, entry.get("kelvin", 3500))
                row.dot_color = [c / 255.0 for c in rgb] + [1.0]
                row.switch.set_state(row.is_on, animate=False)
        finally:
            self._programmatic = False

    # ── Selection ─────────────────────────────────────────────────────────

    def select_all(self):
        self._sel_kind, self._sel_key = "all", None
        self._after_select()

    def select_room(self, name):
        self._sel_kind, self._sel_key = "group", name
        self._after_select()

    def select_bulb(self, serial):
        self._sel_kind, self._sel_key = "bulb", serial
        self._after_select()

    def _after_select(self):
        self._locked_until = 0.0        # a new selection should show its own state
        if self._snapshot is not None:
            self._resolve_selection(self._snapshot)
            self._sync_rows(self._snapshot)
            self._refresh_panel(self._snapshot)

    def _resolve_selection(self, snapshot):
        """Recompute the selected serials - room membership can change under us."""
        bulbs = snapshot["bulbs"]
        if self._sel_kind == "bulb":
            if self._sel_key in bulbs:
                self._sel_serials = [self._sel_key]
                self.sel_title = bulbs[self._sel_key].get("label") or self._sel_key
                self.sel_subtitle = bulbs[self._sel_key].get("group") or "Ungrouped"
                return
            self._sel_kind, self._sel_key = "all", None       # bulb vanished

        if self._sel_kind == "group":
            for room in snapshot["rooms"]:
                if room["name"] == self._sel_key:
                    self._sel_serials = list(room["serials"])
                    self.sel_title = room["name"]
                    self.sel_subtitle = self._count_text(room["count"])
                    return
            self._sel_kind, self._sel_key = "all", None       # room vanished

        self._sel_serials = sorted(bulbs)
        self.sel_title = "All Lights"
        self.sel_subtitle = self._count_text(len(self._sel_serials))

    @staticmethod
    def _count_text(count):
        return "{} light{}".format(count, "" if count == 1 else "s")

    # ── Control panel ─────────────────────────────────────────────────────

    def _refresh_panel(self, snapshot):
        from screens.LIFX.targeting import summarize

        stats = summarize(snapshot["bulbs"], self._sel_serials)
        self.supports_color = stats["supports_color"]

        if not self.supports_color and self.mode == MODE_COLOR:
            self.mode = MODE_WHITE
        self._build_tabs()

        if time.monotonic() >= self._locked_until:
            self.cur_hue = stats["hue"]
            self.cur_sat = stats["saturation"]
            self.cur_bri = stats["brightness"]
            self.cur_kelvin = stats["kelvin"]

        self._programmatic = True
        try:
            self.bri_text = "{}%".format(int(round(self.cur_bri)))
            slider = self.ids.get("brightness_slider")
            if slider is not None:
                slider.value = self.cur_bri
            self._ensure_master_switch(stats["any_on"])
        finally:
            self._programmatic = False

        self._show_mode_panel(stats)

    def _ensure_master_switch(self, is_on):
        if self._master_switch is None:
            self._master_switch = PiHomeSwitch(size=(dp(52), dp(28)))
            self._master_switch.on_change = self._on_master_switch
            holder = self.ids.master_holder
            holder.clear_widgets()
            holder.add_widget(self._master_switch)
        self._master_switch.set_state(is_on, animate=False)

    def _build_tabs(self):
        strip = self.ids.get("tab_strip")
        if strip is None:
            return
        wanted = ([(MODE_COLOR, ICON_PALETTE, "COLOR")] if self.supports_color else []) \
            + [(MODE_WHITE, ICON_SUN, "WHITE"), (MODE_SCENES, ICON_STYLE, "SCENES")]

        strip.clear_widgets()
        self._tabs = {}
        for key, icon, label in wanted:
            tab = ModeTab()
            tab.icon = icon
            tab.label = label
            tab.active = self.mode == key
            tab._apply_theme()
            tab.select_cb = lambda k=key: self.set_mode(k)
            strip.add_widget(tab)
            self._tabs[key] = tab

    def set_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        for key, tab in self._tabs.items():
            tab.active = key == mode
        if self._snapshot is not None:
            self._show_mode_panel(None)

    def _show_mode_panel(self, stats):
        """Swap panels by add/remove - a hidden `disabled` panel eats touches."""
        holder = self.ids.get("mode_holder")
        if holder is None:
            return

        if self.mode == MODE_SCENES:
            signature = tuple(s["id"] for s in (self._snapshot or {}).get("scenes", []))
            if signature != self._scene_signature:
                self._scene_signature = signature
                self._panels.pop(MODE_SCENES, None)

        panel = self._panels.get(self.mode)
        if panel is None:
            builder = {MODE_COLOR: self._build_color_panel,
                       MODE_WHITE: self._build_white_panel,
                       MODE_SCENES: self._build_scenes_panel}[self.mode]
            panel = builder()
            self._panels[self.mode] = panel

        if panel.parent is not holder:
            holder.clear_widgets()
            holder.add_widget(panel)

        self._sync_panel(stats)

    def _sync_panel(self, stats):
        """Push current values into whichever panel is showing."""
        self._programmatic = True
        try:
            wheel = getattr(self, "_wheel", None)
            if wheel is not None:
                wheel.hue = self.cur_hue
                wheel.saturation = self.cur_sat
                wheel.brightness = max(35.0, self.cur_bri)   # keep it legible

            slider = getattr(self, "_kelvin_slider", None)
            if slider is not None:
                low, high = (stats or {}).get("kelvin_range",
                                              (p.KELVIN_MIN, p.KELVIN_MAX))
                slider.min_kelvin, slider.max_kelvin = low, high
                slider.kelvin = p.clamp_kelvin(self.cur_kelvin, low, high)
            readout = getattr(self, "_kelvin_readout", None)
            if readout is not None:
                readout.text = "{}K".format(int(self.cur_kelvin))
            for chip in getattr(self, "_kelvin_chips", []):
                chip.active = abs(chip.kelvin - self.cur_kelvin) < 60
        finally:
            self._programmatic = False

    # ── Panels ────────────────────────────────────────────────────────────

    def _build_color_panel(self):
        panel = BoxLayout(orientation="horizontal", spacing=dp(14))

        self._wheel = ColorWheel(size_hint=(None, 1), width=dp(230))
        self._wheel.bind(on_color_pick=self.on_color_pick)
        panel.add_widget(self._wheel)

        right = BoxLayout(orientation="vertical", spacing=dp(8))
        right.add_widget(Label(
            text="PRESETS", font_name="Nunito", font_size="9sp", bold=True,
            color=self.muted_color, size_hint_y=None, height=dp(14),
            halign="left", valign="middle", text_size=(dp(224), dp(14))))

        # Fixed 4x2 of dp(50) chips. Without an explicit size the grid stretches
        # them to fill the column and they stop reading as swatches.
        grid = GridLayout(cols=4, spacing=dp(8), size_hint=(None, None),
                          size=(dp(224), dp(108)))
        for _name, hue, saturation in _PRESETS:
            rgb = p.hsbk_to_rgb(*p.hsbk_from_pct(hue, saturation, 100, 3500))
            chip = SwatchButton(swatch_color=[c / 255.0 for c in rgb] + [1.0])
            chip.action = lambda h=hue, s=saturation: self.on_swatch(h, s)
            grid.add_widget(chip)
        right.add_widget(grid)
        right.add_widget(Widget())
        panel.add_widget(right)
        return panel

    def _build_white_panel(self):
        panel = BoxLayout(orientation="vertical", spacing=dp(10),
                          padding=(0, dp(6), 0, 0))

        self._kelvin_readout = Label(
            text="{}K".format(int(self.cur_kelvin)), font_name="Nunito",
            font_size="34sp", bold=True, color=self.text_color,
            size_hint_y=None, height=dp(52), halign="center", valign="middle")
        self._kelvin_readout.bind(
            size=lambda i, v: setattr(i, "text_size", i.size))
        panel.add_widget(self._kelvin_readout)

        self._kelvin_slider = KelvinSlider(size_hint_y=None, height=dp(54))
        self._kelvin_slider.bind(on_kelvin_pick=self.on_kelvin_pick)
        panel.add_widget(self._kelvin_slider)

        chips = BoxLayout(orientation="horizontal", spacing=dp(6),
                          size_hint_y=None, height=dp(40))
        self._kelvin_chips = []
        for label, kelvin in _KELVIN_PRESETS:
            chip = KelvinChip()
            chip.label = label
            chip.kelvin = kelvin
            chip._apply_theme()
            chip.select_cb = lambda k=kelvin: self.on_kelvin_preset(k)
            chips.add_widget(chip)
            self._kelvin_chips.append(chip)
        panel.add_widget(chips)
        panel.add_widget(Widget())
        return panel

    def _build_scenes_panel(self):
        panel = BoxLayout(orientation="vertical", spacing=dp(8))
        scenes = (self._snapshot or {}).get("scenes", [])

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3),
                            bar_color=self.accent_color,
                            scroll_type=["bars", "content"])
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None,
                          padding=(0, 0, dp(4), 0))
        grid.bind(minimum_height=grid.setter("height"))

        if not scenes:
            grid.cols = 1
            grid.add_widget(Label(
                text=("No scenes yet.\nSet your lights how you like them, "
                      "then save below."),
                font_name="Nunito", font_size="11sp", color=self.muted_color,
                size_hint_y=None, height=dp(60), halign="center", valign="middle",
                text_size=(dp(460), dp(60))))
        else:
            for scene in scenes:
                card = SceneCard()
                card.scene_id = scene["id"]
                card.label = scene["name"]
                card.source = scene.get("source", "local")
                card._apply_theme()
                card.swatches = scene_swatches(scene)
                card.select_cb = lambda s=scene: self.activate_scene(s)
                card.delete_cb = lambda s=scene: self.confirm_delete_scene(s)
                grid.add_widget(card)
            if len(scenes) % 2 == 1:
                grid.add_widget(Widget())

        scroll.add_widget(grid)
        panel.add_widget(scroll)
        panel.add_widget(self._build_save_row())
        return panel

    def _build_save_row(self):
        row = BoxLayout(orientation="horizontal", spacing=dp(8),
                        size_hint_y=None, height=dp(38))

        self._scene_name = PiTextInput(
            hint_text="Save current lights as...", multiline=False,
            size_hint_y=None, height=dp(34), padding=(dp(10), dp(8)))
        # PiTextInput only themes its text colours; the app-wide rule strips the
        # 9-patch, so without this it renders white-on-white in dark mode.
        self._scene_name.background_normal = ""
        self._scene_name.background_active = ""
        self._scene_name.background_color = list(self.text_color[:3]) + [0.10]
        row.add_widget(self._scene_name)

        save = IconButton(text="\ue161", color=self.accent_color,
                          size_hint_x=None, width=dp(40))
        save.action = self.save_scene
        row.add_widget(save)
        return row

    # ── Handlers ──────────────────────────────────────────────────────────

    def _mark_interaction(self):
        self._locked_until = time.monotonic() + _INTERACTION_LOCK

    def on_color_pick(self, _widget, hue, saturation):
        if self._programmatic:
            return
        self._mark_interaction()
        self.cur_hue, self.cur_sat = hue, saturation
        self._schedule_color_send()

    def _schedule_color_send(self):
        """Leading-edge throttle: send at most every 150ms during a drag."""
        if self._color_send_scheduled:
            return
        self._color_send_scheduled = True
        Clock.schedule_once(lambda dt: self._send_color(), _COLOR_THROTTLE)

    def _send_color(self, final=True):
        self._color_send_scheduled = False
        if self._sel_serials:
            LIFX_SERVICE.set_color(self._sel_serials, self.cur_hue, self.cur_sat,
                                   final=final)

    def on_kelvin_pick(self, _widget, kelvin):
        if self._programmatic:
            return
        self._mark_interaction()
        self.cur_kelvin = kelvin
        self.cur_sat = 0.0
        if self._kelvin_readout is not None:
            self._kelvin_readout.text = "{}K".format(int(kelvin))
        for chip in getattr(self, "_kelvin_chips", []):
            chip.active = abs(chip.kelvin - kelvin) < 60
        if self._sel_serials:
            LIFX_SERVICE.set_kelvin(self._sel_serials, kelvin, final=True)

    def on_kelvin_preset(self, kelvin):
        self.on_kelvin_pick(None, kelvin)

    def on_swatch(self, hue, saturation):
        self._mark_interaction()
        self.cur_hue, self.cur_sat = hue, saturation
        if self._wheel is not None:
            self._programmatic = True
            self._wheel.hue, self._wheel.saturation = hue, saturation
            self._programmatic = False
        self._send_color(final=True)

    def on_brightness_slider(self, value):
        if self._programmatic:
            return
        self._mark_interaction()
        self.cur_bri = value
        self.bri_text = "{}%".format(int(round(value)))
        if self._bri_debounce is not None:
            self._bri_debounce.cancel()
        self._bri_debounce = Clock.schedule_once(
            lambda dt, v=value: self._send_brightness(v), _BRI_DEBOUNCE)

    def _send_brightness(self, value):
        self._bri_debounce = None
        if self._sel_serials:
            LIFX_SERVICE.set_brightness(self._sel_serials, value, final=True)

    def _on_master_switch(self, value):
        if self._programmatic:
            return
        self._mark_interaction()
        if self._sel_serials:
            LIFX_SERVICE.set_power(self._sel_serials, bool(value))

    def _on_room_switch(self, room, value):
        if self._programmatic:
            return
        serials = (sorted((self._snapshot or {}).get("bulbs", {})) if room is None
                   else list(room["serials"]))
        if serials:
            LIFX_SERVICE.set_power(serials, bool(value))

    def _on_bulb_switch(self, serial, value):
        if self._programmatic:
            return
        LIFX_SERVICE.set_power([serial], bool(value))

    # ── Scenes ────────────────────────────────────────────────────────────

    def activate_scene(self, scene):
        def _run():
            result = LIFX_SERVICE.apply_scene(scene["id"])
            message = ("Scene '{}' applied".format(scene["name"]) if result["ok"]
                       else "Scene '{}' partly failed".format(scene["name"]))
            Clock.schedule_once(
                lambda dt: toast(message, "success" if result["ok"] else "warning", 3), 0)

        import threading
        threading.Thread(target=_run, daemon=True, name="lifx-scene").start()

    def save_scene(self):
        name = (self._scene_name.text or "").strip()
        if not name:
            toast("Give the scene a name first", "warning", 3)
            return
        try:
            LIFX_SERVICE.save_scene(name, self._sel_serials or None)
        except ValueError as exc:
            toast(str(exc), "error", 3)
            return
        self._scene_name.text = ""
        toast("Saved scene '{}'".format(name), "success", 3)

    def confirm_delete_scene(self, scene):
        MSGBOX_FACTORY.show(
            title="Delete scene",
            message="Remove '{}'?".format(scene["name"]),
            type=MSGBOX_TYPES["WARNING"],
            buttons=MSGBOX_BUTTONS["YES_NO"],
            on_yes=lambda *a: self._delete_scene(scene),
        )

    def _delete_scene(self, scene):
        if LIFX_SERVICE.remove_scene(scene["id"]):
            toast("Removed '{}'".format(scene["name"]), "info", 3)

    # ── Header actions ────────────────────────────────────────────────────

    def rescan(self):
        LIFX_SERVICE.discover_now()
        toast("Looking for LIFX bulbs...", "info", 3)

    # ── Rotary encoder ────────────────────────────────────────────────────

    def on_rotary_turn(self, direction, button_pressed):
        if not self._sel_serials:
            return False
        value = max(0.0, min(100.0, self.cur_bri + direction * 4.0))
        self._programmatic = True
        slider = self.ids.get("brightness_slider")
        if slider is not None:
            slider.value = value
        self._programmatic = False
        self.on_brightness_slider(value)
        return True

    def on_rotary_pressed(self):
        if not self._sel_serials:
            return False
        bulbs = (self._snapshot or {}).get("bulbs", {})
        any_on = any(bulbs.get(s, {}).get("power") for s in self._sel_serials)
        LIFX_SERVICE.set_power(self._sel_serials, not any_on)
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True


# Attributes the panels create lazily; declared so getattr() checks are cheap
# and a panel that has never been built doesn't raise.
LIFXScreen._wheel = None
LIFXScreen._kelvin_slider = None
LIFXScreen._kelvin_readout = None
LIFXScreen._kelvin_chips = []
LIFXScreen._scene_name = None

PIHOME_LOGGER.info("LIFX screen module loaded")
