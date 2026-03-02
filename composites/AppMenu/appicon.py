from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout

Builder.load_file("./composites/AppMenu/appicon.kv")

class AppIcon(BoxLayout):

    opacity = NumericProperty(0)
    translate_y = NumericProperty(0)
    icon = StringProperty()
    label = StringProperty()

    def __init__(self, icon, label, app_key, on_select, size=(dp(100), dp(118)), **kwargs):
        super(AppIcon, self).__init__(**kwargs)
        self.icon = icon
        self.label = label
        self.app_key = app_key
        self.on_select = on_select
        self.size = size
        self.opacity = 0
        self.translate_y = -dp(28)

    def animate_in(self, delay=0):
        def _start(_dt):
            Animation(opacity=1, translate_y=0, t='out_cubic', d=0.35).start(self)
        Clock.schedule_once(_start, delay)

    def animate_out(self, delay=0, on_complete=None):
        def _start(_dt):
            anim = Animation(opacity=0, translate_y=dp(36), t='in_cubic', d=0.25)
            if on_complete:
                anim.bind(on_complete=lambda *a: on_complete())
            anim.start(self)
        Clock.schedule_once(_start, delay)

    def reset_anim(self):
        Animation.cancel_all(self)
        self.opacity = 0
        self.translate_y = -dp(28)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.on_select(self.app_key)
            return False