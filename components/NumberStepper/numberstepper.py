from kivy.lang import Builder
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

Builder.load_file("./components/NumberStepper/numberstepper.kv")


class NumberStepper(BoxLayout):
    """
    Simple integer stepper with decrement/increment tap targets.
    Pi-safe: no KV canvas blocks, no Line instructions.
    """

    value        = NumericProperty(1)
    min_val      = NumericProperty(0)
    max_val      = NumericProperty(999)
    unit         = StringProperty("")
    accent_color = ColorProperty([0.39, 0.71, 1.0, 1.0])
    text_color   = ColorProperty([1.0,  1.0,  1.0, 0.9])

    def __init__(self, on_change=None, **kwargs):
        super().__init__(**kwargs)
        self._on_change = on_change

    def _set(self, v):
        self.value = max(int(self.min_val), min(int(self.max_val), v))
        if self._on_change:
            self._on_change(self.value)

    def increment(self):
        self._set(self.value + 1)

    def decrement(self):
        self._set(self.value - 1)

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if self.ids.inc_btn.collide_point(*touch.pos):
            self.increment()
            return True
        if self.ids.dec_btn.collide_point(*touch.pos):
            self.decrement()
            return True
        return False
