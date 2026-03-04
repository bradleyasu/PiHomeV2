from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

Builder.load_file("./screens/TaskManagerScreen/taskrow.kv")


class TaskRow(BoxLayout):
    """A single task row for the TaskManagerScreen list."""

    task_id          = StringProperty("")
    task_name        = StringProperty("Task")
    task_description = StringProperty("")
    due_label        = StringProperty("")
    priority_color   = ColorProperty([0.39, 0.71, 1.0, 1.0])
    text_color       = ColorProperty([1.0, 1.0, 1.0, 0.9])
    muted_color      = ColorProperty([1.0, 1.0, 1.0, 0.4])
    accent_color     = ColorProperty([0.39, 0.71, 1.0, 1.0])
    # ObjectProperty so it can be safely passed as a kwarg
    on_delete_cb     = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        # Pull on_delete_cb out before super() so Kivy doesn't misroute it
        cb = kwargs.pop('on_delete_cb', None)
        super().__init__(**kwargs)
        if cb is not None:
            self.on_delete_cb = cb
        Clock.schedule_once(self._build_canvas)

    # ── Python canvas (no KV canvas blocks — safe on Pi GL ES 2.0) ────────────

    def _build_canvas(self, *args):
        strip = self.ids.priority_strip

        # Coloured priority strip
        with strip.canvas:
            self._strip_color = Color(*self.priority_color)
            self._strip_rect  = Rectangle(pos=strip.pos, size=strip.size)
        strip.bind(pos=self._update_strip, size=self._update_strip)
        self.bind(
            priority_color=lambda *a: setattr(self._strip_color, 'rgba', self.priority_color)
        )

        # Bottom row separator (1dp hairline)
        with self.canvas.after:
            self._sep_color = Color(1, 1, 1, 0.06)
            self._sep_rect  = Rectangle(
                pos=(self.x, self.y),
                size=(self.width, dp(1)),
            )
        self.bind(pos=self._update_sep, size=self._update_sep)

    def _update_strip(self, *args):
        strip = self.ids.priority_strip
        self._strip_rect.pos  = strip.pos
        self._strip_rect.size = strip.size

    def _update_sep(self, *args):
        self._sep_rect.pos  = (self.x, self.y)
        self._sep_rect.size = (self.width, dp(1))

    # ── Touch ─────────────────────────────────────────────────────────────────

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if self.ids.delete_lbl.collide_point(*touch.pos):
            if self.on_delete_cb:
                self.on_delete_cb(self.task_id)
            return True
        return False
