from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty
from kivy.animation import Animation
from kivy.uix.widget import Widget
from kivy.metrics import dp

Builder.load_file("./components/Hamburger/hamburger.kv")

class Hamburger(Widget):

    # Animated properties for the ✕ morph
    top_angle       = NumericProperty(0)
    bottom_angle    = NumericProperty(0)
    top_y_offset    = NumericProperty(0)
    bottom_y_offset = NumericProperty(0)
    mid_opacity     = NumericProperty(1)

    is_open = BooleanProperty(False)
    event_handler = None

    def __init__(self, **kwargs):
        super(Hamburger, self).__init__(**kwargs)

    def on_is_open(self, instance, value):
        if value:
            anim = (
                Animation(top_angle=45,     top_y_offset=dp(-11), t='out_cubic', d=0.3)
                & Animation(bottom_angle=-45, bottom_y_offset=dp(11),  t='out_cubic', d=0.3)
                & Animation(mid_opacity=0,  t='linear', d=0.15)
            )
        else:
            anim = (
                Animation(top_angle=0,     top_y_offset=0, t='out_cubic', d=0.3)
                & Animation(bottom_angle=0, bottom_y_offset=0, t='out_cubic', d=0.3)
                & Animation(mid_opacity=1,  t='linear', d=0.2)
            )
        anim.start(self)
        if self.event_handler:
            self.event_handler(value)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.is_open = not self.is_open
            return False
