from kivy.clock import Clock
from kivy.graphics import Color as KColor, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty, ColorProperty, NumericProperty, ObjectProperty, StringProperty,
)
from kivy.uix.label import Label
from kivy.uix.widget import Widget

_ROW_H = dp(46)


class DeviceRow(Widget):
    """A single tappable circuit row: name on the left, live watts on the right,
    with a thin proportional usage bar to convey relative consumption."""

    device_name  = StringProperty("")
    watts        = NumericProperty(0.0)
    watts_text   = StringProperty("0 W")
    sub_text     = StringProperty("")     # optional secondary line (e.g. today's cost)
    fraction     = NumericProperty(0.0)   # 0..1 of the largest consumer
    selected     = BooleanProperty(False)
    on_pressed   = ObjectProperty(None)

    text_color    = ColorProperty([1, 1, 1, 0.92])
    muted_color   = ColorProperty([1, 1, 1, 0.45])
    accent_color  = ColorProperty([0.25, 0.52, 1.0, 1])
    divider_color = ColorProperty([1, 1, 1, 0.07])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = _ROW_H

        self._name_lbl = Label(
            font_name="Nunito", font_size="13sp",
            halign="left", valign="middle",
        )
        self._name_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))

        self._watts_lbl = Label(
            font_name="Nunito", font_size="13sp", bold=True,
            halign="right", valign="middle",
        )
        self._watts_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))

        self._sub_lbl = Label(
            font_name="Nunito", font_size="10sp",
            halign="right", valign="middle",
        )
        self._sub_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))

        self.add_widget(self._name_lbl)
        self.add_widget(self._watts_lbl)
        self.add_widget(self._sub_lbl)

        self.bind(
            pos=self._redraw, size=self._redraw,
            selected=self._redraw, fraction=self._redraw,
            device_name=lambda _, v: setattr(self._name_lbl, "text", v),
            watts_text=lambda _, v: setattr(self._watts_lbl, "text", v),
            sub_text=lambda _, v: (setattr(self._sub_lbl, "text", v), self._redraw()),
            text_color=lambda _, v: setattr(self._name_lbl, "color", v),
            muted_color=lambda _, v: setattr(self._sub_lbl, "color", v),
            accent_color=self._redraw,
        )
        Clock.schedule_once(lambda dt: (
            setattr(self._name_lbl, "text", self.device_name),
            setattr(self._watts_lbl, "text", self.watts_text),
            setattr(self._sub_lbl, "text", self.sub_text),
            self._redraw(),
        ), 0)

    def _redraw(self, *_):
        pad = dp(12)
        self._name_lbl.color = self.text_color
        self._watts_lbl.color = self.accent_color if self.selected else self.text_color
        self._sub_lbl.color = self.muted_color

        self._name_lbl.pos = (self.x + pad, self.y + dp(6))
        self._name_lbl.size = (self.width * 0.55 - pad, self.height - dp(12))

        right_x = self.x + self.width * 0.55
        right_w = self.width * 0.45 - pad
        if self.sub_text:
            self._watts_lbl.pos = (right_x, self.y + self.height * 0.46)
            self._watts_lbl.size = (right_w, self.height * 0.5 - dp(4))
            self._sub_lbl.pos = (right_x, self.y + dp(4))
            self._sub_lbl.size = (right_w, self.height * 0.46 - dp(2))
            self._sub_lbl.opacity = 1
        else:
            self._watts_lbl.pos = (right_x, self.y + dp(6))
            self._watts_lbl.size = (right_w, self.height - dp(12))
            self._sub_lbl.opacity = 0

        self.canvas.before.clear()
        with self.canvas.before:
            if self.selected:
                KColor(rgba=[self.accent_color[0], self.accent_color[1], self.accent_color[2], 0.12])
                RoundedRectangle(
                    pos=(self.x + dp(4), self.y + dp(2)),
                    size=(self.width - dp(8), self.height - dp(4)),
                    radius=[dp(6)],
                )
                KColor(rgba=self.accent_color)
                RoundedRectangle(
                    pos=(self.x + dp(4), self.y + dp(6)),
                    size=(dp(3), self.height - dp(12)),
                    radius=[dp(2)],
                )
            # Proportional usage bar along the bottom of the row
            frac = max(0.0, min(1.0, self.fraction))
            if frac > 0:
                track_w = self.width - dp(24)
                KColor(rgba=[self.accent_color[0], self.accent_color[1], self.accent_color[2], 0.55])
                Rectangle(
                    pos=(self.x + dp(12), self.y + dp(4)),
                    size=(track_w * frac, dp(2)),
                )
            # Bottom separator
            KColor(rgba=self.divider_color)
            Rectangle(pos=(self.x + dp(12), self.y), size=(self.width - dp(24), dp(1)))

    def on_touch_down(self, touch):
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self.on_pressed:
            self.on_pressed(self)
            return True
        return False
