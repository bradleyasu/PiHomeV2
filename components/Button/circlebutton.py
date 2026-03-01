from kivy.app import App
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp

Builder.load_file("./components/Button/circlebutton.kv")

class CircleButton(ButtonBehavior, Widget):
    theme = Theme()
    text = StringProperty()
    custom_font = StringProperty("Nunito")
    color = ColorProperty()
    font_size = NumericProperty('28sp')
    stroke_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    primary_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY, 0))
    down_color = ColorProperty(theme.get_color(theme.TEXT_SECONDARY, 0.18))
    stroke_width = NumericProperty(1.)
    zoom = NumericProperty(1)
    ripple_alpha = NumericProperty(0)

    def __init__(self, size=(dp(50), dp(50)), **kwargs):
        super(CircleButton, self).__init__(**kwargs)
        self.color = self.primary_color
        self.size = size
        self.bind(state=lambda *args: self.animate_state())
        # Entrance: pop in from scale 0
        self.zoom = 0
        Clock.schedule_once(lambda _: self._entrance(), 0.05)

    def _entrance(self):
        Animation(zoom=1, t='out_back', d=0.35).start(self)

    def animate_state(self):
        if self.state == 'down':
            anim = (
                Animation(zoom=0.92, t='out_quad', d=0.08)
                & Animation(color=self.down_color, d=0.08)
                & Animation(ripple_alpha=0.12, d=0.08)
            )
        else:
            anim = (
                Animation(zoom=1, t='out_back', d=0.35)
                & Animation(color=self.primary_color, d=0.25)
                & Animation(ripple_alpha=0, d=0.3)
            )
        anim.start(self)

