"""Pair custom BLE hardware and watch its commands arrive.

The BLE link itself belongs to screens/BluetoothConnect/services/ble_service.py
and runs whether or not this screen is open -- the screen is a window onto it:
pair and forget devices, see which are connected, and watch a live log of the
command tokens they send so you know what to bind.
"""

import time

from kivy.clock import Clock
from kivy.graphics import Color as GColor, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import ColorProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView

from interface.pihomescreen import PiHomeScreen
from theme.theme import Theme
from util.configuration import CONFIG
from util.helpers import toast
from util.phlog import PIHOME_LOGGER

from screens.BluetoothConnect.devicerow import BleDeviceRow
from screens.BluetoothConnect.services.ble_service import BLE_SERVICE

Builder.load_file("./screens/BluetoothConnect/bluetoothconnect.kv")

_TH = Theme()

# MaterialIcons codepoints (all verified present in the bundled font).
_ICON_BT = ""
_ICON_BT_CONNECTED = ""
_ICON_BT_DISABLED = ""
_ICON_BT_SEARCHING = ""
_ICON_SEARCH = ""


class BluetoothConnectScreen(PiHomeScreen):

    # Defaults come from the theme, not literals: this screen is created lazily
    # on first navigation, long after the startup reload_all() that themes every
    # existing screen, so hardcoded colors would paint wrong on the first frame.
    bg_color      = ColorProperty(_TH.get_color(_TH.BACKGROUND_PRIMARY))
    header_color  = ColorProperty(_TH.get_color(_TH.BACKGROUND_SECONDARY))
    text_color    = ColorProperty(_TH.get_color(_TH.TEXT_PRIMARY))
    muted_color   = ColorProperty(_TH.get_color(_TH.TEXT_SECONDARY))
    accent_color  = ColorProperty(_TH.get_color(_TH.ACCENT_PRIMARY))
    status_color  = ColorProperty(_TH.get_color(_TH.TEXT_SECONDARY))
    card_color    = ColorProperty(_TH.get_color(_TH.BACKGROUND_SECONDARY))
    ok_color      = ColorProperty(_TH.get_color(_TH.ALERT_SUCCESS))
    warn_color    = ColorProperty(_TH.get_color(_TH.ALERT_WARNING))

    header_glyph  = StringProperty(_ICON_BT)
    header_status = StringProperty("")
    devices_title = StringProperty("PAIRED DEVICES")
    status_text   = StringProperty("")
    log_hint      = StringProperty("")
    scan_text     = StringProperty("SCAN FOR DEVICES")
    scan_glyph    = StringProperty(_ICON_SEARCH)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._snapshot = None
        self._modal = None
        self._modal_list = None
        self._modal_status = None
        self._modal_seen = set()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_enter(self, *args):
        super().on_enter(*args)
        # Theme first, and only then build children -- rows are handed explicit
        # colors at construction, so anything built earlier would capture the
        # stale defaults and only correct on a later reload_all().
        self.on_config_update(CONFIG)
        BLE_SERVICE.add_listener(self._on_snapshot)
        return None

    def on_pre_leave(self, *args):
        BLE_SERVICE.remove_listener(self._on_snapshot)
        # A scan left running keeps the radio busy and starves reconnects.
        BLE_SERVICE.stop_scan()
        self._dismiss_modal()
        return super().on_pre_leave(*args)

    def on_config_update(self, config):
        # ok/warn are not part of the standard set the base class maps, so they
        # have to be refreshed by hand or they stay stuck on the boot theme.
        theme = Theme()
        self.ok_color = theme.get_color(theme.ALERT_SUCCESS)
        self.warn_color = theme.get_color(theme.ALERT_WARNING)
        # super() applies the standard theme colors, so it goes last.
        super().on_config_update(config)
        if self.is_open:
            self._apply(BLE_SERVICE.get_snapshot())

    # ── Snapshot -> UI ───────────────────────────────────────────────────────

    def _on_snapshot(self, snapshot):
        self._apply(snapshot)

    def _apply(self, snapshot):
        self._snapshot = snapshot
        devices = snapshot.get("devices", [])
        recent = snapshot.get("recent", [])

        connected = [d for d in devices if d.get("connected")]
        self.devices_title = "PAIRED DEVICES ({})".format(len(devices)) if devices \
            else "PAIRED DEVICES"

        if not snapshot.get("available"):
            self.status_text = ("Bluetooth support is still installing.\n"
                                "Restart PiHome to finish setup.")
            self.header_glyph = _ICON_BT_DISABLED
            self.header_status = "not installed"
            self.status_color = self.muted_color
        elif not snapshot.get("enabled"):
            self.status_text = ("Bluetooth is turned off.\n"
                                "Enable it in Settings > Bluetooth Connect.")
            self.header_glyph = _ICON_BT_DISABLED
            self.header_status = "disabled"
            self.status_color = self.muted_color
        elif snapshot.get("scanning"):
            self.status_text = "" if devices else "Scanning for nearby devices..."
            self.header_glyph = _ICON_BT_SEARCHING
            self.header_status = "scanning"
            self.status_color = self.warn_color
        elif not devices:
            self.status_text = ("No devices paired yet.\n"
                                "Tap SCAN to find your hardware.")
            self.header_glyph = _ICON_BT
            self.header_status = snapshot.get("error", "") or "ready"
            self.status_color = self.muted_color
        else:
            self.status_text = ""
            self.header_glyph = _ICON_BT_CONNECTED if connected else _ICON_BT
            self.header_status = "{} of {} connected".format(len(connected), len(devices))
            self.status_color = self.ok_color if connected else self.warn_color

        self.scan_text = "SCANNING..." if snapshot.get("scanning") else "SCAN FOR DEVICES"
        self.log_hint = "" if recent else (
            "Commands from your device show up here.\n"
            "Use the token name when you bind it.")

        self._render_devices(devices)
        self._render_log(recent)

    def _render_devices(self, devices):
        box = self.ids.get("device_box")
        if box is None:
            return
        box.clear_widgets()
        for device in devices:
            row = BleDeviceRow(
                device_name=device.get("name") or "BLE Device",
                address=device.get("address", ""),
                sub_text=self._device_sub(device),
                connected=bool(device.get("connected")),
                text_color=self.text_color,
                muted_color=self.muted_color,
                accent_color=self.accent_color,
                ok_color=self.ok_color,
            )
            # Assign after construction -- an on_* kwarg binds an event
            # instead of setting the property, so the tap would never fire.
            row.on_forget = self._forget_row
            box.add_widget(row)

    @staticmethod
    def _device_sub(device):
        if device.get("error"):
            return device["error"]
        if device.get("connected"):
            last = device.get("last_command")
            if last:
                return "{}  -  last: {}".format(device.get("address", ""), last)
            return device.get("address", "")
        seen = device.get("last_seen") or 0
        if seen:
            return "{}  -  last seen {}".format(
                device.get("address", ""), _ago(seen))
        return "{}  -  never connected".format(device.get("address", ""))

    def _render_log(self, recent):
        box = self.ids.get("log_box")
        if box is None:
            return
        box.clear_widgets()
        for entry in recent[:25]:
            command = entry.get("command", "")
            value = entry.get("value")
            head = command if value is None else "{}: {}".format(command, value)
            result = entry.get("result") or "..."
            label = Label(
                text="{}  {}\n   {}".format(_clock(entry.get("ts", 0)), head, result),
                font_name="Nunito",
                font_size=sp(9),
                color=self.muted_color if result in ("unbound", "...")
                      else self.text_color,
                size_hint_y=None,
                height=dp(30),
                halign="left",
                valign="middle",
            )
            label.bind(size=lambda w, s: setattr(w, "text_size", s))
            box.add_widget(label)

    def _forget_row(self, row):
        response = BLE_SERVICE.forget(row.address)
        toast(response["body"].get("message", "Removed"), "info", 3)

    # ── Discovery ────────────────────────────────────────────────────────────

    def scan_tapped(self, widget, touch):
        if not widget.collide_point(*touch.pos):
            return False
        snapshot = self._snapshot or BLE_SERVICE.get_snapshot()
        if not snapshot.get("available"):
            toast("Bluetooth support is installing - restart PiHome", "warning", 4)
            return True
        if not snapshot.get("enabled"):
            toast("Enable Bluetooth in Settings first", "warning", 3)
            return True
        self._show_discovery_modal()
        return True

    def _show_discovery_modal(self):
        modal = ModalView(size_hint=(0.7, 0.75),
                          background_color=(0, 0, 0, 0),
                          overlay_color=(0, 0, 0, 0.6))
        self._modal = modal
        self._modal_seen = set()

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(8))
        self._redraw_panel(root)
        root.bind(size=lambda w, v: self._redraw_panel(w),
                  pos=lambda w, v: self._redraw_panel(w))

        title_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        glyph = Label(text=_ICON_BT_SEARCHING, font_name="MaterialIcons",
                      font_size=sp(20), color=self.accent_color,
                      size_hint_x=None, width=dp(28))
        title = Label(text="Discover Devices", font_name="Nunito", font_size=sp(14),
                      bold=True, color=self.text_color, halign="left", valign="middle")
        title.bind(size=lambda w, s: setattr(w, "text_size", s))
        title_row.add_widget(glyph)
        title_row.add_widget(title)
        root.add_widget(title_row)

        status = Label(text="Scanning...", font_name="Nunito", font_size=sp(10),
                       color=self.muted_color, size_hint_y=None, height=dp(20),
                       halign="center", valign="middle")
        status.bind(size=lambda w, s: setattr(w, "text_size", s))
        root.add_widget(status)
        self._modal_status = status

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        listing = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        listing.bind(minimum_height=listing.setter("height"))
        scroll.add_widget(listing)
        root.add_widget(scroll)
        self._modal_list = listing

        hint = Label(
            text="Tap a device to pair. Dimmed entries are not advertising the "
                 "PiHome service - check the sketch UUIDs.",
            font_name="Nunito", font_size=sp(8), color=self.muted_color,
            size_hint_y=None, height=dp(26), halign="center", valign="middle")
        hint.bind(size=lambda w, s: setattr(w, "text_size", s))
        root.add_widget(hint)

        modal.add_widget(root)
        modal.open()

        started = BLE_SERVICE.start_scan(
            on_found=self._on_device_found, on_complete=self._on_scan_complete)
        if not started:
            status.text = "Could not start a scan - is Bluetooth enabled?"

    def _redraw_panel(self, widget):
        widget.canvas.before.clear()
        with widget.canvas.before:
            GColor(*(list(self.header_color[:3]) + [0.97]))
            RoundedRectangle(size=widget.size, pos=widget.pos, radius=[dp(10)])

    def _redraw_row(self, widget, compatible):
        alpha = 0.9 if compatible else 0.35
        widget.canvas.before.clear()
        with widget.canvas.before:
            GColor(*(list(self.card_color[:3]) + [alpha]))
            RoundedRectangle(size=widget.size, pos=widget.pos, radius=[dp(6)])

    def _on_device_found(self, device):
        if self._modal_list is None:
            return
        address = device.get("address")
        if address in self._modal_seen:
            return
        self._modal_seen.add(address)

        compatible = bool(device.get("compatible"))
        row = BoxLayout(size_hint_y=None, height=dp(50),
                        spacing=dp(8), padding=(dp(10), 0))
        self._redraw_row(row, compatible)
        row.bind(size=lambda w, v, c=compatible: self._redraw_row(w, c),
                 pos=lambda w, v, c=compatible: self._redraw_row(w, c))

        info = BoxLayout(orientation="vertical", spacing=dp(2))
        name = Label(text=device.get("name") or "Unknown", font_name="Nunito",
                     font_size=sp(11), bold=True,
                     color=self.text_color if compatible else self.muted_color,
                     halign="left", valign="bottom")
        detail = Label(
            text="{}   {} dBm".format(address, device.get("rssi", "?")),
            font_name="Nunito", font_size=sp(8), color=self.muted_color,
            halign="left", valign="top")
        for lbl in (name, detail):
            lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            info.add_widget(lbl)
        row.add_widget(info)

        if device.get("paired"):
            action_text, action_color = "PAIRED", self.muted_color
        elif compatible:
            action_text, action_color = "PAIR", self.accent_color
        else:
            action_text, action_color = "PAIR?", self.muted_color
        action = Label(text=action_text, font_name="Nunito", font_size=sp(10),
                       bold=True, color=action_color, size_hint_x=None,
                       width=dp(60), halign="center", valign="middle")
        action.bind(size=lambda w, s: setattr(w, "text_size", s))
        row.add_widget(action)

        if not device.get("paired"):
            row.bind(on_touch_down=lambda w, t, d=device: self._device_tapped(w, t, d))

        self._modal_list.add_widget(row)
        if self._modal_status is not None:
            self._modal_status.text = "Found {} device(s)...".format(len(self._modal_seen))

    def _on_scan_complete(self, devices):
        if self._modal_status is None:
            return
        if devices:
            self._modal_status.text = "Found {} device(s)".format(len(devices))
        else:
            self._modal_status.text = _empty_scan_message()

    def _device_tapped(self, widget, touch, device):
        if not widget.collide_point(*touch.pos):
            return False
        response = BLE_SERVICE.pair(device.get("address"), device.get("name"))
        toast(response["body"].get("message", "Paired"),
              "success" if response["code"] == 200 else "warning", 3)
        if response["code"] == 200:
            self._dismiss_modal()
        return True

    def _dismiss_modal(self):
        if self._modal is not None:
            try:
                self._modal.dismiss()
            except Exception as e:
                PIHOME_LOGGER.error(f"Bluetooth: could not close the scan dialog: {e}")
        self._modal = None
        self._modal_list = None
        self._modal_status = None

    # ── Rotary encoder ───────────────────────────────────────────────────────

    def on_rotary_turn(self, direction, button_pressed):
        scroll = self.ids.get("device_scroll")
        if scroll is None:
            return False
        scroll.scroll_y = max(0.0, min(1.0, scroll.scroll_y + (0.15 * direction)))
        return True

    def on_rotary_pressed(self):
        snapshot = self._snapshot or BLE_SERVICE.get_snapshot()
        if snapshot.get("available") and snapshot.get("enabled"):
            self._show_discovery_modal()
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True


def _clock(ts):
    if not ts:
        return "--:--:--"
    return time.strftime("%H:%M:%S", time.localtime(ts))


def _ago(ts):
    seconds = max(0, int(time.time() - ts))
    if seconds < 60:
        return "{}s ago".format(seconds)
    if seconds < 3600:
        return "{}m ago".format(seconds // 60)
    if seconds < 86400:
        return "{}h ago".format(seconds // 3600)
    return "{}d ago".format(seconds // 86400)


def _empty_scan_message():
    import sys
    if sys.platform == "darwin":
        return "No devices found - check macOS Bluetooth permission"
    return "No devices found - is the device powered and advertising?"
