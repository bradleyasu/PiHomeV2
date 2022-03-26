from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from components.Button.circlebutton import CircleButton
from theme.color import Color
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from util.tools import hex
from kivy.uix.widget import Widget

Builder.load_file("./composites/PinPad/pinpad.kv")

class PinPad(Widget):

    background_color = ColorProperty((0,0,0,0))
    pinpad_background_color = ColorProperty(Theme().get_color(Theme().BACKGROUND_SECONDARY, 0))
    pinpad_button_color = ColorProperty(hex(Color.INDIGO_600, 1))
    pinpad_opacity = NumericProperty(0)
    y_position = NumericProperty(dp(0))
    code = StringProperty()

    pin_one   = NumericProperty(0)
    pin_two   = NumericProperty(0)
    pin_three = NumericProperty(0)
    pin_four  = NumericProperty(0)

    def __init__(self, on_enter = lambda _: print('enter'), **kwargs):
        super(PinPad, self).__init__(**kwargs)

        pin_grid = self.ids.pin_pad_layout 

        for i in range(9):
           button = CircleButton(text=str(i + 1))
           button.stroke_color = self.pinpad_button_color
           button.text_color = self.pinpad_button_color
           button.bind(on_release=lambda _: self.update_code(str(i + 1)))
           pin_grid.add_widget(button)

        button = CircleButton(text='<')
        button.stroke_color = self.pinpad_button_color
        button.text_color = self.pinpad_button_color
        pin_grid.add_widget(button)

        button = CircleButton(text='0')
        button.stroke_color = self.pinpad_button_color
        button.text_color = self.pinpad_button_color
        pin_grid.add_widget(button)

        button = CircleButton(text='>')
        button.stroke_color = self.pinpad_button_color
        button.text_color = self.pinpad_button_color
        button.bind(on_release=on_enter)
        pin_grid.add_widget(button)


    def update_code(self, ch):
        self.code = self.code + ch
        self.pin_one = 360 if len(self.code) > 0 else 0
        self.pin_two = 360 if len(self.code) > 1 else 0
        self.pin_three = 360 if len(self.code) > 2 else 0
        self.pin_four = 360 if len(self.code) > 3 else 0

    def reset(self):
        self.background_color = (0,0,0,0)
        self.pinpad_background_color = Theme().get_color(Theme().BACKGROUND_SECONDARY, 0)
        self.pinpad_opacity = 0
        self.y_position = dp(0)


    def animate(self):
        animation = Animation(background_color=(0,0,0,0.6), t='out_quad', d=.2)
        animation &= Animation(y_position=(self.height / 2 - dp(225)), t='out_elastic', d=1)
        animation &= Animation(pinpad_background_color=(Theme().get_color(Theme().BACKGROUND_SECONDARY, 1)), t='out_quad', d=.2)
        animation &= Animation(pinpad_opacity=1, t='out_quad', d=.2)
        animation.start(self)
