from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget

Builder.load_file("./composites/AppMenu/appicon.kv")

class AppIcon(Widget):

    background_color = ColorProperty((0,1, 0, 0.0))


    icon = StringProperty()
    def __init__(self, icon, label, app_key, on_select, size=(dp(100), dp(100)), **kwargs):
        super(AppIcon, self).__init__(**kwargs)
        self.icon = icon
        self.label = label
        self.app_key = app_key
        self.on_select = on_select
        self.size = size



    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.on_select(self.app_key)
            return False