import json
import os
import threading
import time
import uuid

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (BooleanProperty, ColorProperty, NumericProperty,
                             StringProperty)
from kivy.uix.floatlayout import FloatLayout

from composites.Notifications.notificationrow import NotificationRow
from services.audio.sfx import SFX
from theme.theme import Theme
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

Builder.load_file("./composites/Notifications/notificationcenter.kv")

_FILE = "cache/notifications.json"
_PANEL_W = dp(360)


class NotificationCenter(FloatLayout):
    """App-wide notification center: a bottom-right bell badge plus a right-side
    slide-in panel listing active notifications.

    Owns the notification model and its persistence (``cache/notifications.json``)
    in addition to its UI — mirrors the ``TIMER_DRAWER`` precedent. Mounted once
    into the root FloatLayout in ``main.py`` and exposed as the module-level
    singleton ``NOTIFICATION_CENTER``.
    """

    count       = NumericProperty(0)
    count_label = StringProperty("")
    panel_open  = BooleanProperty(False)

    # Animated layout drivers (KV binds to these).
    panel_x     = NumericProperty(0)
    panel_width = NumericProperty(_PANEL_W)
    dim_opacity = NumericProperty(0)
    badge_scale = NumericProperty(1.0)   # drives the badge "pop" on reveal

    # ── palette (pulled from the active theme at init) ──────────────────────────
    bg_color     = ColorProperty([0.08, 0.09, 0.13, 1])
    header_color = ColorProperty([0.14, 0.14, 0.16, 1])
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([1, 1, 1, 0.45])
    accent_color = ColorProperty([0.25, 0.52, 1.0, 1])
    danger_color = ColorProperty([0.90, 0.30, 0.30, 1])
    row_bg_color = ColorProperty([1, 1, 1, 0.06])
    # Matches the Weather widget's card/pill surface so the bell badge is
    # visually consistent with the rest of the UI (theme-adaptive).
    card_color        = ColorProperty([0.08, 0.10, 0.14, 1.0])
    card_border_color = ColorProperty([1.0, 1.0, 1.0, 0.10])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, 1)
        self.pos = (0, 0)
        self._notifications = []          # list of notification dicts
        # The badge stays hidden until the Home startup animation finishes
        # (signalled via on_startup_complete), then pops in.
        self._startup_done = False
        self._apply_theme()
        self.panel_width = self._compute_panel_width()
        self.panel_x = Window.width       # start off-screen (right)
        Window.bind(size=self._on_window_size)

    # ── theme ───────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        th = Theme()
        self.bg_color     = th.get_color(th.BACKGROUND_PRIMARY)
        self.header_color = th.get_color(th.BACKGROUND_SECONDARY)
        self.text_color   = th.get_color(th.TEXT_PRIMARY)
        self.muted_color  = th.get_color(th.TEXT_SECONDARY)
        self.accent_color = th.get_color(th.ALERT_INFO)
        self.danger_color = th.get_color(th.BUTTON_DANGER)
        # A subtle row background derived from the secondary background.
        self.row_bg_color = th.get_color(th.BACKGROUND_SECONDARY)
        # Match the Weather widget's card/pill surface + border exactly.
        if th.mode == 1:  # dark
            self.card_color = [0.08, 0.10, 0.14, 1.0]
            self.card_border_color = [1.0, 1.0, 1.0, 0.10]
        else:             # light
            self.card_color = [0.98, 0.98, 0.99, 1.0]
            self.card_border_color = [0.0, 0.0, 0.0, 0.10]

    # ── persistence ─────────────────────────────────────────────────────────────

    def _load(self):
        if not os.path.isfile(_FILE):
            return
        try:
            with open(_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._notifications = data
        except Exception as e:
            PIHOME_LOGGER.error(f"NotificationCenter: load failed: {e}")
            self._notifications = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(_FILE), exist_ok=True)
            with open(_FILE, "w") as f:
                json.dump(self._notifications, f)
        except Exception as e:
            PIHOME_LOGGER.error(f"NotificationCenter: save failed: {e}")

    def on_parent(self, instance, value):
        if value is None:
            return
        self._load()
        # ids are available once the KV rule has been applied.
        Clock.schedule_once(lambda dt: self._refresh(), 0)
        # Defensive last-resort only: the badge reveal is normally driven by the
        # Home startup hook (HomeScreen._after_logo -> on_startup_complete). This
        # timer is deliberately long so it can NEVER race with / fire during the
        # ~11s logo intro; on_startup_complete is idempotent so if the hook
        # already ran this is a no-op.
        Clock.schedule_once(lambda dt: self._startup_fallback(), 30)

    # ── public API (called by NotificationEvent) ────────────────────────────────

    def add(self, notification):
        """Add (or update, by id) a notification. Returns its id.

        Safe to call from any thread — UI mutation is deferred to the Kivy main
        thread via Clock (events fire on MQTT/HTTP/socket background threads).
        """
        nid = notification.get("id") or uuid.uuid4().hex
        notification["id"] = nid
        notification.setdefault("ts", time.time())
        Clock.schedule_once(lambda dt: self._add_main(notification), 0)
        return nid

    def _add_main(self, notification):
        nid = notification["id"]
        is_new = True
        for i, n in enumerate(self._notifications):
            if n.get("id") == nid:
                self._notifications[i] = notification     # update in place
                is_new = False
                break
        else:
            self._notifications.append(notification)

        max_active = max(1, CONFIG.get_int("notifications", "max_active", 50))
        if len(self._notifications) > max_active:
            self._notifications = self._notifications[-max_active:]

        self._save()
        self._refresh()

        # Audible cue for a genuinely new notification (not an upsert/update,
        # and not when restoring persisted notifications on launch).
        if is_new:
            try:
                SFX.play("pop")
            except Exception as e:
                PIHOME_LOGGER.error(f"NotificationCenter: SFX play failed: {e}")

    def dismiss(self, nid):
        self._notifications = [n for n in self._notifications if n.get("id") != nid]
        self._save()
        self._refresh()

    def clear_all(self):
        self._notifications = []
        self._save()
        self._refresh()

    # ── UI refresh ──────────────────────────────────────────────────────────────

    def _refresh(self):
        self.count = len(self._notifications)
        self._rebuild_rows()
        self._update_badge()

    def _rebuild_rows(self):
        if "rows_box" not in self.ids:
            return
        box = self.ids.rows_box
        box.clear_widgets()
        # Newest on top.
        for n in reversed(self._notifications):
            row = NotificationRow(
                n,
                text_color=self.text_color,
                muted_color=self.muted_color,
                row_bg_color=self.row_bg_color,
                danger_color=self.danger_color,
            )
            # Assign callbacks AFTER construction (CLAUDE.md gotcha #11).
            row.select_cb = (lambda nid=n["id"], ev=n.get("event"):
                             self._on_row_tap(nid, ev))
            row.clear_cb = (lambda nid=n["id"]: self.dismiss(nid))
            box.add_widget(row)

    def _update_badge(self):
        if "badge" not in self.ids:
            return
        self.count_label = "9+" if self.count > 9 else str(self.count)
        badge = self.ids.badge
        if self.count <= 0:
            Animation.cancel_all(badge, "opacity")
            Animation(opacity=0, d=0.2).start(badge)
            return
        # Keep the badge hidden until the startup animation has finished.
        if not self._startup_done:
            Animation.cancel_all(badge, "opacity")
            badge.opacity = 0
            return
        # Pop in only when transitioning from hidden -> visible; a pure count
        # change while already visible should not re-trigger the animation.
        if badge.opacity < 1:
            self._pop_badge()

    def _pop_badge(self):
        """Reveal the badge with a scale 'pop' (overshoot via out_back)."""
        badge = self.ids.badge
        Animation.cancel_all(badge, "opacity")
        Animation.cancel_all(self, "badge_scale")
        badge.opacity = 1
        self.badge_scale = 0.0
        Animation(badge_scale=1.0, t="out_back", d=0.45).start(self)

    def on_startup_complete(self):
        """Called once the Home startup animation has revealed the controls.

        Idempotent: only the first call reveals the badge, so the Home hook and
        the defensive fallback can't double-trigger the pop.
        """
        if self._startup_done:
            return
        self._startup_done = True
        if self.count > 0:
            self._pop_badge()

    def _startup_fallback(self):
        if not self._startup_done:
            self.on_startup_complete()

    def on_count(self, instance, value):
        self.count_label = "9+" if value > 9 else str(value)

    # ── row interaction ─────────────────────────────────────────────────────────

    def _on_row_tap(self, nid, event):
        if event:
            threading.Thread(
                target=self._fire_event, args=(event,),
                daemon=True, name="notification-event"
            ).start()
        # Auto-dismiss after tap.
        self.dismiss(nid)

    def _fire_event(self, event):
        try:
            from events.pihomeevent import PihomeEventFactory
            PihomeEventFactory.create_event_from_dict(event).execute()
        except Exception as e:
            PIHOME_LOGGER.error(f"NotificationCenter: event fire failed: {e}")

    # ── panel open/close ────────────────────────────────────────────────────────

    def _compute_panel_width(self):
        return min(_PANEL_W, Window.width * 0.85)

    def open_panel(self):
        if self.count <= 0:
            return
        self.panel_open = True
        self.panel_width = self._compute_panel_width()
        Animation.cancel_all(self, "panel_x", "dim_opacity")
        Animation(panel_x=Window.width - self.panel_width,
                  dim_opacity=0.6, t="out_quad", d=0.28).start(self)

    def close_panel(self):
        self.panel_open = False
        Animation.cancel_all(self, "panel_x", "dim_opacity")
        Animation(panel_x=Window.width, dim_opacity=0,
                  t="in_quad", d=0.24).start(self)

    def _on_window_size(self, window, size):
        self.panel_width = self._compute_panel_width()
        if self.panel_open:
            self.panel_x = Window.width - self.panel_width
        else:
            self.panel_x = Window.width

    # ── touch routing ───────────────────────────────────────────────────────────
    # The center is full-screen (size_hint 1,1) and sits above the screen
    # manager, so it MUST pass touches through when the panel is closed,
    # intercepting only the small badge.

    def on_touch_down(self, touch):
        if self.panel_open:
            # Tap on the dim backdrop (left of the panel) closes it.
            if touch.x < self.panel_x:
                self.close_panel()
                return True
            super().on_touch_down(touch)
            return True
        # Panel closed: only the badge is interactive.
        if self.count > 0 and "badge" in self.ids and \
                self.ids.badge.collide_point(*touch.pos):
            self.open_panel()
            return True
        return False

    def on_touch_move(self, touch):
        if self.panel_open:
            super().on_touch_move(touch)
            return True
        return False

    def on_touch_up(self, touch):
        if self.panel_open:
            super().on_touch_up(touch)
            return True
        return False


NOTIFICATION_CENTER = NotificationCenter()
