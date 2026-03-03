import os
import pickle
import time

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (BooleanProperty, ColorProperty, ListProperty,
                              NumericProperty, StringProperty)
from kivy.uix.boxlayout import BoxLayout

from components.PihomeTimer.pihometimer import PiHomeTimer
from services.audio.sfx import SFX
from services.timers.timer import Timer
from util.phlog import PIHOME_LOGGER

Builder.load_file("./composites/TimerDrawer/timerdrawer.kv")

_PILL_H  = dp(64)
_ROW_H   = dp(54)   # must match PiHomeTimer.height in kv


class TimerDrawer(BoxLayout):

    cache_file   = "timers.pihome"
    timer_widgets = ListProperty([])

    # ── pill header display (updated by _tick at 10 Hz) ──────────────────────
    primary_label    = StringProperty("")
    primary_time     = StringProperty("--:--:--")
    primary_progress = NumericProperty(1.0)   # 1.0 = full → 0.0 = done
    extra_count      = NumericProperty(0)     # timers beyond the primary one

    expanded = BooleanProperty(False)

    # ── palette ───────────────────────────────────────────────────────────────
    bg_color     = ColorProperty([0.08, 0.09, 0.13, 0.94])
    row_bg_color = ColorProperty([0.11, 0.13, 0.18, 0.97])
    accent_color = ColorProperty([0.39, 0.71, 1.00, 1.00])
    text_color   = ColorProperty([1.00, 1.00, 1.00, 0.90])
    muted_color  = ColorProperty([1.00, 1.00, 1.00, 0.40])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint   = (None, None)
        self.width       = dp(360)
        self.height      = _PILL_H
        # Start well below the visible screen; y is updated in _show_drawer
        self.pos         = (0, -dp(600))
        self.in_position = False
        self._tick_event = Clock.schedule_interval(self._tick, 1.0)
        # Re-centre horizontally whenever the window is resized
        Window.bind(size=self._on_window_size)

    # ── persistence ───────────────────────────────────────────────────────────

    def on_parent(self, instance, value):
        if value is not None:
            try:
                self.deserialize()
            except Exception as e:
                PIHOME_LOGGER.error(f"TimerDrawer: deserialize error: {e}")

    def serialize(self):
        timers = [tw.timer.to_dict() for tw in self.timer_widgets if tw.timer]
        with open(self.cache_file, 'wb') as f:
            pickle.dump(timers, f)
        PIHOME_LOGGER.info(f"TimerDrawer: serialized {len(timers)} timers")

    def deserialize(self):
        if not os.path.exists(self.cache_file):
            return
        with open(self.cache_file, 'rb') as f:
            timers = pickle.load(f)
        for d in timers:
            elapsed   = time.time() - d["start_time"]
            remaining = d["duration"] - elapsed
            if remaining <= 0:
                continue
            timer = Timer(remaining, d["label"], d["on_complete"])
            self.add_timer(timer)
        PIHOME_LOGGER.info(f"TimerDrawer: restored {len(self.timer_widgets)} timers")

    # ── timer management ──────────────────────────────────────────────────────

    def add_timer(self, timer):
        self._ensure_width()
        tw = PiHomeTimer(timer=timer)
        self.timer_widgets.append(tw)
        # if 'tray' in self.ids:
        #     self.ids.tray.add_widget(tw)
        # timer.add_listener(
        #     lambda _: Clock.schedule_once(lambda dt: self._on_timer_done(tw), 0)
        # )
        # tw.start()
        # self._refresh()
        # try:
        #     self.serialize()
        # except Exception as e:
        #     PIHOME_LOGGER.error(f"TimerDrawer: serialize error: {e}")

    def _on_timer_done(self, tw):
        if tw in self.timer_widgets:
            self.timer_widgets.remove(tw)
        if 'tray' in self.ids and tw.parent:
            self.ids.tray.remove_widget(tw)
        SFX.play("success")
        self._refresh()
        try:
            self.serialize()
        except Exception as e:
            PIHOME_LOGGER.error(f"TimerDrawer: serialize error: {e}")

    def create_timer(self, duration, label, on_complete=None):
        timer = Timer(duration, label, on_complete)
        self.add_timer(timer)
        SFX.play("pop")

    # ── layout helpers ────────────────────────────────────────────────────────

    def _on_window_size(self, window, size):
        """Keep the drawer horizontally centred after a window resize."""
        self._recenter_x()

    def _recenter_x(self):
        app_w = Window.width
        if app_w <= 0:
            return
        self.width = min(dp(380), app_w - dp(32))
        self.x     = (app_w - self.width) / 2.0

    def _ensure_width(self):
        self._recenter_x()

    def _refresh(self):
        """Recalculate size and show/hide the drawer after any timer count change."""
        n = len(self.timer_widgets)
        if n == 0:
            self._hide_drawer()
            return
        if n <= 1 and self.expanded:
            # Non-animated collapse — don't waste time on animation here
            self.expanded = False
        self._show_drawer()

    def on_expanded(self, instance, value):
        """Animate the tray open or closed, keeping the pill header stationary."""
        if not self.in_position:
            return
        n          = len(self.timer_widgets)
        new_height = _PILL_H + (_ROW_H * n if value else 0)
        target_y   = Window.height - new_height
        Animation(height=new_height, y=target_y, t='out_quad', d=0.28).start(self)

    def on_height(self, instance, value):
        """Keep ids.tray.height in sync with the drawer height during animation."""
        if 'tray' not in self.ids:
            return
        tray_h = max(0.0, value - _PILL_H)
        self.ids.tray.height   = tray_h
        self.ids.tray.opacity  = 1.0 if tray_h > dp(4) else 0.0

    def _show_drawer(self):
        self._ensure_width()
        app_h      = Window.height
        n          = len(self.timer_widgets)
        new_height = _PILL_H + (_ROW_H * n if self.expanded else 0)
        self.height = new_height
        target_y   = app_h - new_height
        if not self.in_position:
            self.y = app_h   # start just above the screen edge
        self.in_position = True
        Animation(y=target_y, t='out_back', d=0.4).start(self)

    def _hide_drawer(self):
        self.in_position = False
        self.expanded    = False
        Animation(y=Window.height, t='in_back', d=0.35).start(self)

    # ── Touch routing ─────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        # Pill always receives touches
        if 'pill' in self.ids:
            self.ids.pill.dispatch('on_touch_down', touch)
        # Tray rows only receive touches when the tray is open
        if self.expanded and 'tray' in self.ids:
            self.ids.tray.dispatch('on_touch_down', touch)
        return True

    def on_touch_move(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if self.expanded and 'tray' in self.ids:
            self.ids.tray.dispatch('on_touch_move', touch)
        return True

    # ── pill right-button action ──────────────────────────────────────────────

    def _pill_right_action(self):
        """Right-side pill button: cancel if single timer, expand/collapse if multiple."""
        if len(self.timer_widgets) == 1:
            self.timer_widgets[0]._do_cancel()
        elif len(self.timer_widgets) > 1:
            self.expanded = not self.expanded

    # ── 10-Hz pill refresh ────────────────────────────────────────────────────

    def _tick(self, dt):
        if not self.timer_widgets:
            return

        def _rem(tw):
            t = tw.timer
            if t and t.is_running:
                return t.duration - t.get_elapsed_time()
            return float('inf')

        first = min(self.timer_widgets, key=_rem)
        self.primary_label    = first.label
        self.primary_time     = first.time_label
        self.primary_progress = first.progress
        self.extra_count      = max(0, len(self.timer_widgets) - 1)
        self.accent_color     = list(first.accent_color)

    # ── shutdown ──────────────────────────────────────────────────────────────

    def shutdown(self):
        if self._tick_event:
            self._tick_event.cancel()
        for tw in self.timer_widgets:
            if tw.timer and tw.timer.is_running:
                tw.timer.is_running = False


TIMER_DRAWER = TimerDrawer()
