from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.properties import (
    NumericProperty, ColorProperty, BooleanProperty, StringProperty,
)
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Line
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp

from components.Msgbox.msgbox import MSGBOX_FACTORY, MSGBOX_BUTTONS
from services.qr.qr import QR
from system.brightness import get_brightness, set_brightness
from screens.DevTools.sysinfo import get_local_ip
from theme.theme import Theme
from util.const import SERVER_PORT
from util.phlog import PIHOME_LOGGER


class CharmWidget(Widget):
    """Windows 8-style charms drawer that slides in from the right edge.

    Contains a brightness slider and action icons.  Designed to be extended
    with additional controls in the future.
    """

    # Animation state
    _drawer_x = NumericProperty(0.0)
    _scrim_alpha = NumericProperty(0.0)
    is_open = BooleanProperty(False)

    # Brightness
    _brightness = NumericProperty(50)
    _brightness_text = StringProperty("50%")

    # Theme
    _bg_color = ColorProperty([0.08, 0.08, 0.10, 0.95])
    _accent_color = ColorProperty([0.3, 0.7, 1.0, 1])
    _text_color = ColorProperty([1, 1, 1, 1])
    _muted_color = ColorProperty([1, 1, 1, 0.4])
    _icon_color = ColorProperty([1, 1, 1, 0.85])
    _danger_color = ColorProperty([1.0, 0.35, 0.3, 1])

    # Layout constants
    DRAWER_WIDTH = dp(72)
    ICON_SIZE = dp(36)
    ICON_SPACING = dp(24)
    SLIDER_WIDTH = dp(14)
    SLIDER_HEIGHT = dp(160)
    CORNER_RADIUS = dp(12)
    EDGE_ZONE = dp(5)       # right-edge touch zone for swipe-to-open
    SWIPE_THRESHOLD = dp(40) # minimum horizontal swipe distance to trigger open

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = Window.size
        self.pos = (0, 0)

        self._visible = False
        self._anim = None
        self._touch_active = False
        self._edge_swipe_touch = None  # tracks an in-progress edge swipe

        # Start with drawer off-screen
        w = Window.size[0]
        self._drawer_x = w + self.DRAWER_WIDTH

        # Action items: (icon_codepoint, label, callback, color_property_name)
        # New items can be appended to this list before the drawer opens.
        self._actions = [
            ("\ue00a", "Web", self._action_show_qr, "_accent_color"),
            ("\ue86a", "Restart", self._action_restart_pihome, "_icon_color"),
            ("\ue8ac", "Reboot", self._action_reboot, "_danger_color"),
        ]

        # QR overlay state
        self._qr_overlay = None

        self._brightness = get_brightness()
        self._brightness_text = "{}%".format(int(self._brightness))

        self._build_canvas()
        self._build_labels()

        self.bind(_drawer_x=self._update_positions)
        self.bind(_scrim_alpha=self._update_scrim)
        self.bind(_brightness=self._on_brightness)
        Window.bind(size=self._on_window_resize)

    # ── Canvas setup ────────────────────────────────────────────────────

    def _build_canvas(self):
        w, h = Window.size
        dw = self.DRAWER_WIDTH
        dx = w + dw  # start off-screen

        with self.canvas:
            # Scrim (full-screen dim overlay)
            self._scrim_color = Color(0, 0, 0, 0)
            self._scrim_rect = Rectangle(pos=(0, 0), size=(w, h))

            # Drawer background
            self._drawer_bg_color = Color(*self._bg_color)
            self._drawer_bg = RoundedRectangle(
                pos=(dx, 0),
                size=(dw, h),
                radius=[self.CORNER_RADIUS, 0, 0, self.CORNER_RADIUS],
            )

            # Subtle left border accent
            self._border_color = Color(*self._accent_color[:3], 0.15)
            self._border_line = Line(
                points=[dx, dp(12), dx, h - dp(12)],
                width=1,
            )

        # Build slider track/fill on canvas.after
        self._build_slider_canvas()
        # Build action icon background circles on canvas.after
        self._build_action_canvas()

    def _build_slider_canvas(self):
        w, h = Window.size
        dw = self.DRAWER_WIDTH
        dx = w + dw
        sw = self.SLIDER_WIDTH
        sh = self.SLIDER_HEIGHT

        sx = dx + (dw - sw) / 2.0
        sy = h / 2.0 + dp(10)

        with self.canvas.after:
            # Slider track
            self._slider_track_color = Color(1, 1, 1, 0.08)
            self._slider_track = RoundedRectangle(
                pos=(sx, sy), size=(sw, sh),
                radius=[dp(7)],
            )
            # Slider fill
            self._slider_fill_color = Color(*self._accent_color)
            fill_h = sh * self._brightness / 100.0
            self._slider_fill = RoundedRectangle(
                pos=(sx, sy), size=(sw, max(dp(7), fill_h)),
                radius=[dp(7)],
            )

        self._slider_pos = (sx, sy)
        self._slider_size = (sw, sh)

    def _build_action_canvas(self):
        """Build background circles for action icons."""
        w, h = Window.size
        dw = self.DRAWER_WIDTH
        dx = w + dw
        icon_s = self.ICON_SIZE
        spacing = self.ICON_SPACING

        center_x = dx + dw / 2.0
        start_y = h / 2.0 + dp(10) - dp(50)

        self._action_gfx = []

        with self.canvas.after:
            for i, (icon, label, callback, color_attr) in enumerate(self._actions):
                y = start_y - i * (icon_s + spacing)

                bg_color = Color(1, 1, 1, 0.06)
                bg_ellipse = Ellipse(
                    pos=(center_x - icon_s / 2.0, y - icon_s / 2.0),
                    size=(icon_s, icon_s),
                )

                self._action_gfx.append({
                    "bg_color": bg_color,
                    "bg_ellipse": bg_ellipse,
                    "center": (center_x, y),
                    "icon": icon,
                    "label": label,
                    "callback": callback,
                    "color_attr": color_attr,
                })

    def _build_labels(self):
        """Create Label widgets for icons and text overlays."""
        w, h = Window.size
        dw = self.DRAWER_WIDTH
        dx = w + dw
        sw = self.SLIDER_WIDTH
        sh = self.SLIDER_HEIGHT
        icon_s = self.ICON_SIZE

        # Brightness icon (sun) above slider
        sx = dx + (dw - sw) / 2.0
        sy = h / 2.0 + dp(10)
        self._bright_icon_label = Label(
            text="\ue518",  # brightness_high
            font_name="MaterialIcons",
            font_size=sp(18),
            color=self._muted_color,
            size_hint=(None, None),
            size=(dw, dp(24)),
            pos=(dx, sy + sh + dp(4)),
            halign="center",
            valign="middle",
        )
        self._bright_icon_label.text_size = self._bright_icon_label.size
        self.add_widget(self._bright_icon_label)

        # Brightness percentage text below slider
        self._bright_text_label = Label(
            text=self._brightness_text,
            font_name="Nunito",
            font_size=sp(9),
            color=self._muted_color,
            size_hint=(None, None),
            size=(dw, dp(18)),
            pos=(dx, sy - dp(22)),
            halign="center",
            valign="middle",
        )
        self._bright_text_label.text_size = self._bright_text_label.size
        self.add_widget(self._bright_text_label)

        # Action icon labels
        self._action_labels = []
        center_x = dx + dw / 2.0
        start_y = h / 2.0 + dp(10) - dp(50)
        spacing = self.ICON_SPACING

        for i, gfx in enumerate(self._action_gfx):
            y = start_y - i * (icon_s + spacing)
            color = getattr(self, gfx["color_attr"])

            # Icon label (MaterialIcons)
            icon_label = Label(
                text=gfx["icon"],
                font_name="MaterialIcons",
                font_size=sp(18),
                color=color,
                size_hint=(None, None),
                size=(icon_s, icon_s),
                pos=(center_x - icon_s / 2.0, y - icon_s / 2.0),
                halign="center",
                valign="middle",
            )
            icon_label.text_size = icon_label.size
            self.add_widget(icon_label)

            # Text label below the icon
            text_label = Label(
                text=gfx["label"],
                font_name="Nunito",
                font_size=sp(8),
                color=self._muted_color,
                size_hint=(None, None),
                size=(dw, dp(14)),
                pos=(dx, y - icon_s / 2.0 - dp(14)),
                halign="center",
                valign="middle",
            )
            text_label.text_size = text_label.size
            self.add_widget(text_label)

            self._action_labels.append({
                "icon_label": icon_label,
                "text_label": text_label,
                "color_attr": gfx["color_attr"],
            })

    # ── Position updates ───────────────────────────────────────────────

    def _update_positions(self, *_args):
        dx = self._drawer_x
        h = Window.size[1]
        dw = self.DRAWER_WIDTH
        sw, sh = self._slider_size
        icon_s = self.ICON_SIZE
        spacing = self.ICON_SPACING

        # Drawer background
        self._drawer_bg.pos = (dx, 0)
        self._drawer_bg.size = (dw, h)
        self._border_line.points = [dx, dp(12), dx, h - dp(12)]

        # Slider
        sx = dx + (dw - sw) / 2.0
        sy = h / 2.0 + dp(10)
        self._slider_track.pos = (sx, sy)
        self._slider_track.size = (sw, sh)
        fill_h = sh * self._brightness / 100.0
        self._slider_fill.pos = (sx, sy)
        self._slider_fill.size = (sw, max(dp(7), fill_h))
        self._slider_pos = (sx, sy)

        # Brightness icon label
        self._bright_icon_label.pos = (dx, sy + sh + dp(4))
        # Brightness text label
        self._bright_text_label.pos = (dx, sy - dp(22))

        # Action icons
        center_x = dx + dw / 2.0
        start_y = h / 2.0 + dp(10) - dp(50)

        for i, gfx in enumerate(self._action_gfx):
            y = start_y - i * (icon_s + spacing)
            gfx["bg_ellipse"].pos = (center_x - icon_s / 2.0, y - icon_s / 2.0)
            gfx["center"] = (center_x, y)

            # Update label positions
            al = self._action_labels[i]
            al["icon_label"].pos = (center_x - icon_s / 2.0, y - icon_s / 2.0)
            al["text_label"].pos = (dx, y - icon_s / 2.0 - dp(14))

    def _update_scrim(self, *_args):
        self._scrim_color.a = self._scrim_alpha

    def _on_brightness(self, *_args):
        val = int(self._brightness)
        self._brightness_text = "{}%".format(val)
        self._bright_text_label.text = self._brightness_text
        sh = self.SLIDER_HEIGHT
        fill_h = sh * self._brightness / 100.0
        self._slider_fill.size = (self._slider_size[0], max(dp(7), fill_h))

    def _on_window_resize(self, _win, size):
        w, h = size
        self.size = (w, h)
        self._scrim_rect.size = (w, h)
        if not self.is_open:
            self._drawer_x = w + self.DRAWER_WIDTH
        self._update_positions()

    # ── Theme ──────────────────────────────────────────────────────────

    def update_theme(self):
        th = Theme()
        self._bg_color = list(th.get_color(th.BACKGROUND_SECONDARY))[:3] + [0.95]
        self._accent_color = th.get_color(th.ALERT_INFO)
        self._text_color = th.get_color(th.TEXT_PRIMARY)
        self._muted_color = th.get_color(th.TEXT_SECONDARY)
        self._danger_color = th.get_color(th.ALERT_DANGER)

        self._drawer_bg_color.rgba = self._bg_color
        self._slider_fill_color.rgba = self._accent_color
        self._bright_icon_label.color = self._muted_color
        self._bright_text_label.color = self._muted_color

        for al in self._action_labels:
            al["icon_label"].color = getattr(self, al["color_attr"])
            al["text_label"].color = self._muted_color

    # ── Open / Close ───────────────────────────────────────────────────

    def toggle(self):
        if self.is_open:
            self.close()
        else:
            self.open()

    def open(self):
        if self.is_open:
            return
        self.is_open = True
        self._visible = True
        self._brightness = get_brightness()

        Animation.cancel_all(self)
        target_x = Window.size[0] - self.DRAWER_WIDTH
        anim = Animation(_drawer_x=target_x, t="out_cubic", d=0.25)
        anim &= Animation(_scrim_alpha=0.35, t="out_cubic", d=0.25)
        anim.start(self)

    def close(self):
        if not self.is_open:
            return
        self.is_open = False

        Animation.cancel_all(self)
        target_x = Window.size[0] + self.DRAWER_WIDTH
        anim = Animation(_drawer_x=target_x, t="in_cubic", d=0.2)
        anim &= Animation(_scrim_alpha=0.0, t="in_cubic", d=0.2)

        def _on_done(*_args):
            self._visible = False

        anim.bind(on_complete=_on_done)
        anim.start(self)

    # ── Touch handling ─────────────────────────────────────────────────

    def on_touch_down(self, touch):
        # ── Edge-swipe detection (drawer closed) ──
        if not self._visible:
            w = Window.size[0]
            if touch.x >= w - self.EDGE_ZONE:
                self._edge_swipe_touch = touch.uid
                touch.ud["charm_edge_ox"] = touch.x
                return True  # grab the touch
            return False

        dx = self._drawer_x
        dw = self.DRAWER_WIDTH

        # Check if touch is inside the drawer
        if dx <= touch.x <= dx + dw:
            # Check slider — use a wider hit area for easier touch
            sx, sy = self._slider_pos
            sw, sh = self._slider_size
            hit_margin = dp(20)
            if (sx - hit_margin) <= touch.x <= (sx + sw + hit_margin) and sy <= touch.y <= sy + sh:
                self._touch_active = True
                self._set_brightness_from_touch(touch.y)
                return True

            # Check action icons
            icon_s = self.ICON_SIZE
            for gfx in self._action_gfx:
                cx, cy = gfx["center"]
                if abs(touch.x - cx) <= icon_s / 2.0 and abs(touch.y - cy) <= icon_s / 2.0:
                    gfx["bg_color"].a = 0.2
                    Clock.schedule_once(lambda dt, g=gfx: self._reset_icon_bg(g), 0.15)
                    gfx["callback"]()
                    return True

            return True  # consume touch inside drawer

        # Touch outside drawer — close it
        self.close()
        return True

    def on_touch_move(self, touch):
        # ── Edge-swipe tracking ──
        if self._edge_swipe_touch == touch.uid:
            ox = touch.ud.get("charm_edge_ox", touch.x)
            if ox - touch.x >= self.SWIPE_THRESHOLD:
                self._edge_swipe_touch = None
                self.open()
            return True

        if self._touch_active:
            self._set_brightness_from_touch(touch.y)
            return True
        return False

    def on_touch_up(self, touch):
        # ── Edge-swipe cancel ──
        if self._edge_swipe_touch == touch.uid:
            self._edge_swipe_touch = None
            return True

        if self._touch_active:
            self._touch_active = False
            return True
        return False

    def _set_brightness_from_touch(self, y):
        sx, sy = self._slider_pos
        sh = self.SLIDER_HEIGHT
        pct = max(5, min(100, (y - sy) / sh * 100.0))
        self._brightness = pct
        set_brightness(int(pct))

    def _reset_icon_bg(self, gfx):
        gfx["bg_color"].a = 0.06

    # ── Rotary encoder support ─────────────────────────────────────────

    def adjust_brightness(self, delta):
        """Adjust brightness by delta (e.g., +5 or -5). Called from rotary turn."""
        new_val = max(5, min(100, self._brightness + delta))
        self._brightness = new_val
        set_brightness(int(new_val))

    # ── Actions ────────────────────────────────────────────────────────

    def _action_show_qr(self):
        self.close()
        Clock.schedule_once(lambda dt: self._show_qr_overlay(), 0.25)

    def _show_qr_overlay(self):
        if self._qr_overlay is not None:
            return

        ip = get_local_ip()
        url = "http://{}:{}".format(ip, SERVER_PORT)

        try:
            qr_path = QR().from_url(url, filename="charm_qr.png")
        except Exception as e:
            PIHOME_LOGGER.error("CharmWidget: QR generation failed: {}".format(e))
            return

        overlay = Widget(size=Window.size, pos=(0, 0), size_hint=(None, None))

        # Scrim background
        with overlay.canvas:
            Color(0, 0, 0, 0.75)
            Rectangle(pos=(0, 0), size=Window.size)

            # Card background
            card_w, card_h = dp(260), dp(310)
            card_x = (Window.size[0] - card_w) / 2.0
            card_y = (Window.size[1] - card_h) / 2.0
            Color(*self._bg_color[:3], 0.95)
            RoundedRectangle(
                pos=(card_x, card_y),
                size=(card_w, card_h),
                radius=[dp(12)],
            )

        # QR image
        qr_size = dp(200)
        qr_img = Image(
            source=qr_path,
            size_hint=(None, None),
            size=(qr_size, qr_size),
            pos=((Window.size[0] - qr_size) / 2.0, card_y + dp(70)),
            allow_stretch=True,
            keep_ratio=True,
        )
        overlay.add_widget(qr_img)

        # Title
        title = Label(
            text="Scan to connect",
            font_name="Nunito",
            font_size=sp(14),
            bold=True,
            color=self._text_color,
            size_hint=(None, None),
            size=(card_w, dp(24)),
            pos=(card_x, card_y + card_h - dp(36)),
            halign="center",
            valign="middle",
        )
        title.text_size = title.size
        overlay.add_widget(title)

        # URL text
        url_label = Label(
            text=url,
            font_name="Nunito",
            font_size=sp(10),
            color=self._accent_color,
            size_hint=(None, None),
            size=(card_w, dp(20)),
            pos=(card_x, card_y + dp(38)),
            halign="center",
            valign="middle",
        )
        url_label.text_size = url_label.size
        overlay.add_widget(url_label)

        # Dismiss hint
        hint = Label(
            text="Tap anywhere to dismiss",
            font_name="Nunito",
            font_size=sp(8),
            color=self._muted_color,
            size_hint=(None, None),
            size=(card_w, dp(16)),
            pos=(card_x, card_y + dp(14)),
            halign="center",
            valign="middle",
        )
        hint.text_size = hint.size
        overlay.add_widget(hint)

        # Dismiss on touch
        def dismiss_qr(instance, touch):
            self._dismiss_qr_overlay()
            return True

        overlay.bind(on_touch_down=dismiss_qr)

        self._qr_overlay = overlay

        # Add to root window's parent (same level as CHARM)
        parent = self.parent
        if parent:
            parent.add_widget(overlay)

    def _dismiss_qr_overlay(self):
        if self._qr_overlay is None:
            return
        if self._qr_overlay.parent:
            self._qr_overlay.parent.remove_widget(self._qr_overlay)
        self._qr_overlay = None

    def _action_restart_pihome(self):
        self.close()

        def do_restart():
            from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
            PIHOME_LOGGER.info("CharmWidget: Restarting PiHome")
            PIHOME_SCREEN_MANAGER.goto("_shutdown")

        MSGBOX_FACTORY.show(
            "Restart PiHome",
            "Restart the PiHome service?",
            0, 1, MSGBOX_BUTTONS["YES_NO"],
            on_yes=do_restart,
        )

    def _action_reboot(self):
        self.close()

        def do_reboot():
            import subprocess
            PIHOME_LOGGER.info("CharmWidget: Rebooting system")
            try:
                subprocess.Popen(
                    ["sudo", "reboot"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                PIHOME_LOGGER.error("CharmWidget: Reboot failed: {}".format(e))

        MSGBOX_FACTORY.show(
            "Reboot System",
            "Reboot the Raspberry Pi? PiHome will restart automatically.",
            0, 1, MSGBOX_BUTTONS["YES_NO"],
            on_yes=do_reboot,
        )


CHARM = CharmWidget()
