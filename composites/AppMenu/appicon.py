from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty, NumericProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout

Builder.load_file("./composites/AppMenu/appicon.kv")

class AppIcon(BoxLayout):

    background_color = ColorProperty((0,1, 0, 0))

    y_pos_offset = NumericProperty(-20)
    opacity = NumericProperty(0)
    zoom = NumericProperty(0.7)
    icon = StringProperty()
    label = StringProperty()
    def __init__(self, icon, label, app_key, on_select, size=(dp(100), dp(100)), delay = 0, **kwargs):
        super(AppIcon, self).__init__(**kwargs)
        self.icon = icon
        self.label = label
        self.app_key = app_key
        self.on_select = on_select
        self.size = size
        Clock.schedule_once(lambda _: self.animate(), delay)


    def animate(self):
        animation = Animation(y_pos_offset = 0, t='out_elastic', d=1)
        animation &= Animation(opacity = 1, t='out_elastic', d=10)
        animation &= Animation(zoom = 1, t='out_elastic', d=1)
        animation.start(self)


    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.on_select(self.app_key)
            return False