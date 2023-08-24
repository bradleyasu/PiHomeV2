from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty, NumericProperty, BooleanProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.clock import Clock

Builder.load_file("./screens/CommandCenter/commandbutton.kv")

class CommandButton(Widget):

    background_color = ColorProperty((0,1, 0, 0))
    y_pos_offset = NumericProperty(-20)
    opacity = NumericProperty(0)
    zoom = NumericProperty(0.7)
    icon = StringProperty()
    label = StringProperty()

    is_running = BooleanProperty(False)
    is_success = BooleanProperty(False)
    is_error = BooleanProperty(False)
    
    success_icon = StringProperty("./screens/CommandCenter/icons/success.png")
    running_icon = StringProperty("./screens/CommandCenter/icons/running.png")
    error_icon = StringProperty("./screens/CommandCenter/icons/error.png")
    default_icon = StringProperty("./screens/CommandCenter/icons/default.png")

    def __init__(self, icon, label, app_key, on_select, size=(dp(100), dp(100)), delay = 0, **kwargs):
        super(CommandButton, self).__init__(**kwargs)
        self.icon = self.default_icon
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


    def show_success(self):
        self.icon = self.success_icon
        Clock.schedule_once(lambda _: self.reset_state(), 10)

    def show_error(self):
        self.icon = self.error_icon
        Clock.schedule_once(lambda _: self.reset_state(), 10)

    def show_running(self):
        self.is_running = True
        self.icon = self.running_icon

    
    def reset_state(self):
        self.is_running = False
        self.icon = self.default_icon

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and not self.is_running:
            self.show_running()
            Clock.schedule_once(lambda _: self.on_select(self), 1)
            return False