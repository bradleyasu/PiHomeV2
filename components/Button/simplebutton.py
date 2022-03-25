from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget

Builder.load_file("./components/Button/simplebutton.kv")

class SimpleButton(ButtonBehavior, Widget):
    background_color = ColorProperty()
    foreground_color = ColorProperty()
    pressed_color = ColorProperty()
    text = StringProperty()
    zoom = NumericProperty(1)

    def __init__(self, type = Theme().BUTTON_PRIMARY, **kwargs):
       super(SimpleButton, self).__init__(**kwargs)
       
       self.background_color = Theme().get_color(type)
       self.foreground_color = Theme().get_color(Theme().TEXT_PRIMARY)
       self.pressed_color = Theme().get_color(type)
       self.bind(state=lambda *args: self.animate())

    def animate(self):
        if self.state == 'down':
            animation = Animation(zoom=.9, t='out_quad', d=.2)
        else:
            animation = Animation(zoom=1, t='out_elastic', d=.5)
        animation.start(self)


