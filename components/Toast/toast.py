from kivy.lang import Builder
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp

Builder.load_file("./components/Toast/toast.kv")

LEVEL_ICONS = {
    "info":    "\ue88e",   # info
    "default": "\ue88e",
    "warn":    "\ue002",   # warning
    "warning": "\ue002",
    "error":   "\ue000",   # error
    "danger":  "\ue000",
    "success": "\ue86c",   # check_circle
    "done":    "\ue86c",
}


class Toast(Widget):
    theme = Theme()
    text = StringProperty("")
    icon = StringProperty(LEVEL_ICONS["info"])
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background_color = ColorProperty(theme.get_color(theme.ALERT_INFO, 0.92))
    border_color = ColorProperty(theme.get_color(theme.ALERT_INFO, 0.35))
    info_color = ColorProperty(theme.get_color(theme.ALERT_INFO, 0.92))
    warning_color = ColorProperty(theme.get_color(theme.ALERT_WARNING, 0.92))
    error_color = ColorProperty(theme.get_color(theme.ALERT_DANGER, 0.92))
    success_color = ColorProperty(theme.get_color(theme.ALERT_SUCCESS, 0.92))
    info_border = ColorProperty(theme.get_color(theme.ALERT_INFO, 0.35))
    warning_border = ColorProperty(theme.get_color(theme.ALERT_WARNING, 0.35))
    error_border = ColorProperty(theme.get_color(theme.ALERT_DANGER, 0.35))
    success_border = ColorProperty(theme.get_color(theme.ALERT_SUCCESS, 0.35))
    zoom = NumericProperty(0.8)
    opacity = NumericProperty(0)
    y_pos_offset = NumericProperty(-20)

    _scheduled_events = []
    _dismissed = False

    def __init__(self, on_reset, size=(dp(740), dp(50)), pos=(dp(30), dp(30)), **kwargs):
        super(Toast, self).__init__(**kwargs)
        self.size = size
        self.pos = pos
        self.on_reset = on_reset
        self._scheduled_events = []
        self._dismissed = False

    def pop(self, label, level="info", timeout=5):
        self._cancel_pending()
        self._dismissed = False

        Animation.cancel_all(self)
        self.opacity = 0
        self.zoom = 0.8
        self.y_pos_offset = -20

        self.text = label
        self.icon = LEVEL_ICONS.get(level, LEVEL_ICONS["info"])

        if level in ("info", "default"):
            self.background_color = self.info_color
            self.border_color = self.info_border
        elif level in ("warn", "warning"):
            self.background_color = self.warning_color
            self.border_color = self.warning_border
        elif level in ("error", "danger"):
            self.background_color = self.error_color
            self.border_color = self.error_border
        elif level in ("success", "done"):
            self.background_color = self.success_color
            self.border_color = self.success_border

        ev1 = Clock.schedule_once(lambda _: self._animate_in(), 0.1)
        self._scheduled_events.append(ev1)

        if timeout > 0:
            ev2 = Clock.schedule_once(lambda _: self._dismiss(), timeout)
            self._scheduled_events.append(ev2)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._dismiss()
            return True

    def _animate_in(self):
        anim = Animation(y_pos_offset=0, t='out_expo', d=0.3)
        anim &= Animation(opacity=1, t='out_cubic', d=0.3)
        anim &= Animation(zoom=1, t='out_expo', d=0.3)
        anim.start(self)

    def _dismiss(self):
        if self._dismissed:
            return
        self._dismissed = True
        self._cancel_pending()

        anim = Animation(opacity=0, t='out_cubic', d=0.4)
        anim &= Animation(y_pos_offset=-10, t='out_cubic', d=0.4)
        anim.bind(on_complete=lambda *_: self._on_dismiss_complete())
        anim.start(self)

    def _on_dismiss_complete(self):
        self.on_reset()

    def _cancel_pending(self):
        for ev in self._scheduled_events:
            ev.cancel()
        self._scheduled_events.clear()
