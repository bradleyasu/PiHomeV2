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

    def dismiss(self, on_done=None):
        """Animate out, then remove self from parent."""
        if on_done is not None:
            Clock.schedule_once(lambda _: on_done(), 0.28)

        def _remove(*_):
            if self.parent:
                self.parent.remove_widget(self)

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
        Create and display a Msgbox as the topmost widget in the app.
        Returns the Msgbox instance.
        """
        box = Msgbox()
        box.title   = title
        box.message = message
        box.type    = type
        box.set_buttons(buttons, on_yes, on_no)

        # Add to the root layout at index 0 — topmost in the draw stack
        app = get_app()
        app.layout.add_widget(box, index=0)
        box.show()

        if timeout > 0:
            Clock.schedule_once(lambda _: box.dismiss(), timeout)

        self.msgbox = box
        return box


MSGBOX_FACTORY = MsgboxFactory()
