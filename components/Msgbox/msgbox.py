from collections import deque

from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, ColorProperty
from services.audio.sfx import SFX
from kivy.animation import Animation
from components.Button.simplebutton import SimpleButton
from theme.theme import Theme
from kivy.clock import Clock

from util.helpers import get_app

Builder.load_file("./components/Msgbox/msgbox.kv")

MSGBOX_TYPES = {
    "ERROR": 0,
    "WARNING": 1,
    "INFO": 2,
    "SUCCESS": 3,
}

MSGBOX_BUTTONS = {
    "OK": 0,
    "YES_NO": 1,
}

# Material Icons codepoints
_ICONS = {
    MSGBOX_TYPES["ERROR"]:   "\ue000",   # error
    MSGBOX_TYPES["WARNING"]: "\ue002",   # warning
    MSGBOX_TYPES["INFO"]:    "\ue88e",   # info
    MSGBOX_TYPES["SUCCESS"]: "\ue86c",   # check_circle
}

_ACCENT_KEY = {
    MSGBOX_TYPES["ERROR"]:   lambda t: t.ALERT_DANGER,
    MSGBOX_TYPES["WARNING"]: lambda t: t.ALERT_WARNING,
    MSGBOX_TYPES["INFO"]:    lambda t: t.ALERT_INFO,
    MSGBOX_TYPES["SUCCESS"]: lambda t: t.ALERT_SUCCESS,
}


class MsgboxCard(BoxLayout):
    """Card widget — owns its own canvas drawing and scale/opacity animation."""
    card_scale    = NumericProperty(0.88)
    card_opacity  = NumericProperty(0.0)
    card_color    = ColorProperty([1, 1, 1, 1])
    border_color  = ColorProperty([0, 0, 0, 1])
    accent_color  = ColorProperty([0, 0, 0, 1])
    divider_color = ColorProperty([0, 0, 0, 1])
    text_primary  = ColorProperty([0, 0, 0, 1])
    text_secondary = ColorProperty([0, 0, 0, 1])
    type_icon     = StringProperty("")
    title         = StringProperty("")
    message       = StringProperty("")


class Msgbox(FloatLayout):
    _theme = Theme()

    scrim_color = ColorProperty([0, 0, 0, 0])

    # Content
    title   = StringProperty("Title")
    message = StringProperty("Message")
    type    = NumericProperty(MSGBOX_TYPES["INFO"])
    buttons = NumericProperty(MSGBOX_BUTTONS["OK"])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # KV rule has already run, ids is populated
        self._card = self.ids.card
        # Set by MsgboxFactory to advance the queue when this box is dismissed
        self._factory_cb    = None
        self._countdown_event  = None
        self._countdown_widget = None

    # ── Internal helpers ───────────────────────────────────────────────────

    def _refresh_theme(self):
        """Pull current theme colors (respects light/dark mode) onto the card."""
        t = Theme()
        card = self._card
        card.card_color    = t.get_color(t.COLOR_SECONDARY)
        card.border_color  = t.get_color(t.COLOR_PRIMARY)
        card.text_primary  = t.get_color(t.TEXT_PRIMARY)
        card.text_secondary = t.get_color(t.TEXT_SECONDARY)
        card.divider_color = t.get_color(t.COLOR_PRIMARY)

        accent_fn = _ACCENT_KEY.get(self.type, lambda t: t.ALERT_INFO)
        card.accent_color = t.get_color(accent_fn(t))
        card.type_icon    = _ICONS.get(self.type, _ICONS[MSGBOX_TYPES["INFO"]])
        card.title        = self.title
        card.message      = self.message

    def _play_sfx(self):
        if self.type == MSGBOX_TYPES["ERROR"]:
            SFX.play("error")

    # ── Public API ─────────────────────────────────────────────────────────

    def show(self):
        """Size to window, refresh theme, then animate in."""
        app = get_app()
        self.size = (app.width, app.height)
        self.pos  = (0, 0)
        # Force layout NOW so pos_hint centers the card before animation starts.
        # FloatLayout._trigger_layout is async (next frame); we need it sync.
        self.do_layout()
        self._refresh_theme()
        self._play_sfx()

        card = self._card
        card.card_scale   = 0.88
        card.card_opacity = 0.0

        anim_scrim = Animation(scrim_color=[0, 0, 0, 0.6], t='linear', d=0.22)
        anim_card  = Animation(card_scale=1.0, card_opacity=1.0, t='out_expo', d=0.38)
        anim_scrim.start(self)
        anim_card.start(card)

    def _start_countdown(self, timeout):
        """Overlay a shrinking pie-sector on the card's bottom-right corner.

        Uses only Ellipse (safe on Pi VideoCore IV).  Two layers:
          1. A faint full circle as a background track.
          2. A filled pie sector (angle_end shrinks from 360° to 0°) that
             drains clockwise as time runs out.

        Visibility is tied to card_opacity so the indicator fades in/out
        in perfect sync with the card's show and dismiss animations.
        The clock doesn't start until the card's in-animation finishes so
        the widget is never visible before the card has fully appeared.
        """
        from kivy.graphics import Color, Ellipse as GlEllipse

        SIZE    = dp(28)
        total   = float(timeout)
        elapsed = [0.0]
        # Capture accent color now — _refresh_theme() has already run in show()
        accent  = list(self._card.accent_color)

        dot = Widget(size_hint=(None, None), size=(SIZE, SIZE))
        dot.opacity = 0  # invisible until card_opacity binds it up
        self.add_widget(dot)
        self._countdown_widget = dot

        # Sync dot opacity to the card's animated opacity property.
        # This makes the indicator fade in with the show animation and
        # fade out automatically during dismiss — no extra work needed.
        self._card.bind(
            card_opacity=lambda inst, val: setattr(dot, 'opacity', val)
        )

        def _update(*_):
            frac = max(0.0, 1.0 - elapsed[0] / total)
            # Anchor to card bottom-right, 4dp inset so it sits inside the border
            card = self._card
            dot.pos = (card.right - SIZE - dp(4), card.y + dp(4))
            px, py  = dot.pos
            dot.canvas.clear()
            with dot.canvas:
                # Background track
                Color(1, 1, 1, 0.15)
                GlEllipse(pos=(px, py), size=(SIZE, SIZE))
                # Foreground countdown sector — drains clockwise from the top
                Color(*accent)
                GlEllipse(
                    pos=(px, py), size=(SIZE, SIZE),
                    angle_start=90,
                    angle_end=90 + 360.0 * frac,
                )

        def _tick(dt):
            elapsed[0] += dt
            _update()
            if elapsed[0] >= total:
                if self._countdown_event:
                    self._countdown_event.cancel()
                    self._countdown_event = None

        def _begin(*_):
            # Guard: box may have been dismissed before the delay fired
            if self._countdown_event is None:
                return
            self._countdown_event = None
            _update()
            # ~20 fps — readable animation, gentle on Pi GPU
            self._countdown_event = Clock.schedule_interval(_tick, 1.0 / 20.0)

        # Delay first draw + interval start until the card in-animation
        # completes (d=0.38s), so the indicator never flashes before the card.
        # Store the schedule_once handle in _countdown_event so that dismiss()
        # cancels it cleanly if the box is dismissed before it fires.
        self._countdown_event = Clock.schedule_once(_begin, 0.38)

    def dismiss(self, on_done=None):
        """Animate out, then remove self from parent and fire on_done.

        on_done can be:
          - None        → nothing happens
          - a callable  → called directly (programmatic usage)
          - a dict      → treated as a PiHome event dict and executed via
                          PihomeEventFactory (webhook / task usage)
        """
        # Stop the countdown clock (no-op if it was never started)
        if self._countdown_event:
            self._countdown_event.cancel()
            self._countdown_event = None

        def _fire_on_done():
            if on_done is None:
                return
            if callable(on_done):
                on_done()
            elif isinstance(on_done, dict):
                try:
                    from events.pihomeevent import PihomeEventFactory
                    PihomeEventFactory.create_event_from_dict(on_done).execute()
                except Exception as e:
                    from util.phlog import PIHOME_LOGGER
                    PIHOME_LOGGER.error(f"Msgbox: failed to execute on_done event: {e}")

        if on_done is not None:
            Clock.schedule_once(lambda _: _fire_on_done(), 0.28)

        def _remove(*_):
            if self.parent:
                self.parent.remove_widget(self)
            if self._factory_cb:
                self._factory_cb()

        card = self._card
        anim_scrim = Animation(scrim_color=[0, 0, 0, 0], t='linear', d=0.22)
        anim_card  = Animation(card_scale=0.92, card_opacity=0.0, t='out_quad', d=0.25)
        anim_scrim.start(self)
        anim_card.bind(on_complete=_remove)
        anim_card.start(card)

    def set_buttons(self, buttons, on_yes=None, on_no=None):
        self.buttons = buttons
        Clock.schedule_once(
            lambda _: self._build_buttons(buttons, on_yes, on_no), 0
        )

    def _build_buttons(self, buttons, on_yes, on_no):
        t = Theme()
        card = self._card
        grid = card.ids.button_grid
        grid.clear_widgets()

        accent      = card.accent_color
        btn_text    = t.get_color(t.BUTTON_PRIMARY_TEXT)
        btn_sec_bg  = t.get_color(t.BUTTON_SECONDARY)
        btn_sec_txt = t.get_color(t.TEXT_PRIMARY)

        if buttons == MSGBOX_BUTTONS["OK"]:
            btn = SimpleButton(text="OK", size_hint=(None, 1), width=dp(80))
            btn.background_color = accent
            btn.foreground_color = btn_text
            btn.bind(on_press=lambda _: self.dismiss())
            grid.add_widget(btn)

        elif buttons == MSGBOX_BUTTONS["YES_NO"]:
            yes_btn = SimpleButton(text="YES", size_hint=(None, 1), width=dp(80))
            yes_btn.background_color = accent
            yes_btn.foreground_color = btn_text
            yes_btn.bind(on_press=lambda _: self.dismiss(on_yes))

            no_btn = SimpleButton(text="NO", size_hint=(None, 1), width=dp(80))
            no_btn.background_color = btn_sec_bg
            no_btn.foreground_color = btn_sec_txt
            no_btn.bind(on_press=lambda _: self.dismiss(on_no))

            grid.add_widget(yes_btn)
            grid.add_widget(no_btn)

    # ── Touch: absorb all touches; tap outside card dismisses (OK only) ───

    def on_touch_down(self, touch):
        card = self._card
        if card and not card.collide_point(*touch.pos) and self.buttons == MSGBOX_BUTTONS["OK"]:
            self.dismiss()
            return True
        super().on_touch_down(touch)
        return True

    def on_touch_move(self, touch):
        return True

    def on_touch_up(self, touch):
        super().on_touch_up(touch)
        return True


# ── Factory ────────────────────────────────────────────────────────────────

class MsgboxFactory:
    """Singleton factory that ensures only one Msgbox is on screen at a time.

    Subsequent show() calls while a box is active are enqueued and displayed
    in FIFO order as each box is dismissed (by user or timeout).
    """

    def __init__(self):
        self._queue  = deque()   # pending entries
        self._active = None      # currently visible Msgbox, or None
        self.msgbox  = None      # last shown box (legacy accessor)

    # ── Public API ──────────────────────────────────────────────────────────

    def show(
        self,
        title,
        message,
        timeout=0,
        type=MSGBOX_TYPES["INFO"],
        buttons=MSGBOX_BUTTONS["OK"],
        on_yes=None,
        on_no=None,
    ):
        """
        Display a Msgbox, or enqueue it if one is already on screen.
        Returns None when enqueued (box hasn't been created yet).
        """
        entry = dict(
            title=title, message=message, timeout=timeout,
            type=type, buttons=buttons, on_yes=on_yes, on_no=on_no,
        )
        if self._active is None:
            return self._show_entry(entry)
        else:
            self._queue.append(entry)
            return None

    # ── Internal ────────────────────────────────────────────────────────────

    def _show_entry(self, entry):
        box = Msgbox()
        box.title   = entry['title']
        box.message = entry['message']
        box.type    = entry['type']
        box.set_buttons(entry['buttons'], entry['on_yes'], entry['on_no'])
        box._factory_cb = self._on_dismissed

        app = get_app()
        app.layout.add_widget(box, index=0)
        box.show()

        if entry['timeout'] > 0:
            box._start_countdown(entry['timeout'])
            Clock.schedule_once(lambda _: box.dismiss(), entry['timeout'])

        self._active = box
        self.msgbox  = box
        return box

    def _on_dismissed(self):
        """Called by the active Msgbox after it removes itself from the tree."""
        self._active = None
        if self._queue:
            next_entry = self._queue.popleft()
            # Small delay so the outgoing animation fully clears before the
            # next card animates in — avoids visual overlap on slow hardware.
            Clock.schedule_once(lambda _: self._show_entry(next_entry), 0.15)


MSGBOX_FACTORY = MsgboxFactory()
