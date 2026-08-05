from kivy.clock import Clock
from kivy.graphics import Color as KColor, Ellipse, Rectangle
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty, ColorProperty, ObjectProperty, StringProperty,
)
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from theme.theme import Theme

_ROW_H = dp(52)
_FORGET_W = dp(40)

_TH = Theme()


class BleDeviceRow(Widget):
    """One paired BLE device: status dot, name, address / last activity, and a
    trailing forget button."""

    device_name = StringProperty("")
    address     = StringProperty("")
    sub_text    = StringProperty("")
    connected   = BooleanProperty(False)

    # Assign these AFTER construction -- passing an on_* property as a kwarg
    # binds it as an event instead of setting it (Kivy EventDispatcher rule).
    on_pressed = ObjectProperty(None)
    on_forget  = ObjectProperty(None)

    text_color    = ColorProperty(_TH.get_color(_TH.TEXT_PRIMARY))
    muted_color   = ColorProperty(_TH.get_color(_TH.TEXT_SECONDARY))
    accent_color  = ColorProperty(_TH.get_color(_TH.ACCENT_PRIMARY))
    ok_color      = ColorProperty(_TH.get_color(_TH.ALERT_SUCCESS))
    divider_color = ColorProperty([1, 1, 1, 0.07])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = _ROW_H

        self._name_lbl = Label(font_name="Nunito", font_size="13sp", bold=True,
                               halign="left", valign="middle")
        self._sub_lbl = Label(font_name="Nunito", font_size="9sp",
                              halign="left", valign="middle")
        self._forget_lbl = Label(text="", font_name="MaterialIcons",
                                 font_size="16sp", halign="center", valign="middle")
        for lbl in (self._name_lbl, self._sub_lbl, self._forget_lbl):
            lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            self.add_widget(lbl)

        self.bind(
            pos=self._redraw, size=self._redraw, connected=self._redraw,
            device_name=lambda _, v: setattr(self._name_lbl, "text", v),
            sub_text=lambda _, v: setattr(self._sub_lbl, "text", v),
            text_color=self._redraw, muted_color=self._redraw,
            accent_color=self._redraw, ok_color=self._redraw,
        )
        Clock.schedule_once(lambda dt: (
            setattr(self._name_lbl, "text", self.device_name),
            setattr(self._sub_lbl, "text", self.sub_text),
            self._redraw(),
        ), 0)

    def _redraw(self, *_):
        dot = dp(8)
        left = self.x + dp(12)
        text_x = left + dot + dp(10)
        text_w = self.width - (text_x - self.x) - _FORGET_W - dp(8)

        self._name_lbl.color = self.text_color
        self._sub_lbl.color = self.muted_color
        self._forget_lbl.color = self.muted_color

        self._name_lbl.pos = (text_x, self.y + self.height * 0.46)
        self._name_lbl.size = (text_w, self.height * 0.5 - dp(4))
        self._sub_lbl.pos = (text_x, self.y + dp(5))
        self._sub_lbl.size = (text_w, self.height * 0.46 - dp(2))
        self._forget_lbl.pos = (self.right - _FORGET_W, self.y)
        self._forget_lbl.size = (_FORGET_W, self.height)

        self.canvas.before.clear()
        with self.canvas.before:
            KColor(rgba=self.ok_color if self.connected
                   else [self.muted_color[0], self.muted_color[1], self.muted_color[2], 0.5])
            Ellipse(pos=(left, self.center_y - dot / 2.0), size=(dot, dot))
            KColor(rgba=self.divider_color)
            Rectangle(pos=(self.x + dp(12), self.y), size=(self.width - dp(24), dp(1)))

    def on_touch_down(self, touch):
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if touch.x >= self.right - _FORGET_W:
            if self.on_forget:
                self.on_forget(self)
            return True
        if self.on_pressed:
            self.on_pressed(self)
        return True
