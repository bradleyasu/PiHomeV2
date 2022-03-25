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

    backgrounds={
        'primary': Theme().BUTTON_PRIMARY,
        'secondary': Theme().BUTTON_SECONDARY
    }
    foregrounds={
        'primary': Theme().BUTTON_PRIMARY_TEXT,
        'secondary': Theme().BUTTON_SECONDARY_TEXT
    }
    accents={
        'primary': Theme().BUTTON_PRIMARY_ACCENT,
        'secondary': Theme().BUTTON_SECONDARY_ACCENT
    }

    def __init__(self, type = "primary", **kwargs):
       super(SimpleButton, self).__init__(**kwargs)
       
       self.background_color = Theme().get_color(self.backgrounds[type])
       self.foreground_color = Theme().get_color(self.foregrounds[type])
       self.pressed_color = Theme().get_color(self.accents[type])
       self.bind(state=lambda *args: self.animate())

    def animate(self):
        if self.state == 'down':
            animation = Animation(zoom=.9, t='out_quad', d=.2)
        else:
            animation = Animation(zoom=1, t='out_elastic', d=.5)
        animation.start(self)


