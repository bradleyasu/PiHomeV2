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
from util.helpers import get_app
from util.tools import hex
from kivy.uix.widget import Widget

Builder.load_file("./composites/PinPad/pinpad.kv")

class PinPad(Widget):

    background_color = ColorProperty((0,0,0,0))
    pinpad_background_color = ColorProperty(Theme().get_color(Theme().BACKGROUND_SECONDARY, 0))
    pinpad_button_color = ColorProperty(hex(Color.INDIGO_600, 1))
    pinpad_opacity = NumericProperty(0)
    y_position = NumericProperty(0)
    code = StringProperty()

    pin_one   = NumericProperty(0)
    pin_two   = NumericProperty(0)
    pin_three = NumericProperty(0)
    pin_four  = NumericProperty(0)

    def __init__(self, pin = '', on_enter = lambda _: print('enter'), **kwargs):
        super(PinPad, self).__init__(**kwargs)
        self.pin = pin
        self.on_enter = on_enter

        app_size = App.get_running_app().get_size()
        self.ids.pin_pad_float_container.size = app_size
        pin_grid = self.ids.pin_pad_layout 
        pin_grid.bind(on_touch_down=lambda x,y:self.touch_check(x,y))

        for i in range(9):
           button = CircleButton(text=str(i + 1))
           button.stroke_color = self.pinpad_button_color
           button.text_color = self.pinpad_button_color
           button.bind(on_release=lambda x: self.update_code(x.text))
           pin_grid.add_widget(button)

        button = CircleButton(text='DELETE')
        button.bind(on_release=self.backspace)
        button.stroke_color = self.pinpad_background_color
        button.text_color = self.pinpad_button_color
        button.font_size = '10sp'
        pin_grid.add_widget(button)

        button = CircleButton(text='0')
        button.stroke_color = self.pinpad_button_color
        button.text_color = self.pinpad_button_color
        button.bind(on_release=lambda x: self.update_code(x.text))
        pin_grid.add_widget(button)

        button = CircleButton(text='UNLOCK')
        button.stroke_color = self.pinpad_background_color
        button.text_color = self.pinpad_button_color
        button.font_size = '10sp'
        button.bind(on_release=self.verify_pin)
        pin_grid.add_widget(button)
        self.reset()

    def verify_pin(self, *args):
        if self.code == self.pin:
            self.on_enter()
        else:
            self.code = ""
            self.refresh_pins()
        
    def backspace(self, *args):
        self.code = self.code[:-1]
        self.refresh_pins()

    def update_code(self, ch):
        self.code = self.code + ch
        if len(self.code) > 4:
            self.verify_pin()
        self.refresh_pins()

    def refresh_pins(self):
        self.pin_one = 360 if len(self.code) > 0 else 0
        self.pin_two = 360 if len(self.code) > 1 else 0
        self.pin_three = 360 if len(self.code) > 2 else 0
        self.pin_four = 360 if len(self.code) > 3 else 0

    def reset(self):
        self.code = ""
        self.refresh_pins()
        self.background_color = (0,0,0,0)
        self.pinpad_background_color = Theme().get_color(Theme().BACKGROUND_SECONDARY, 0)
        self.pinpad_opacity = 0
        self.y_position = dp(get_app().width - 100)
        self.height = dp(get_app().height/3 - 40)


    def animate(self):
        animation = Animation(background_color=(0,0,0,0.6), t='linear', d=.2)
        animation &= Animation(y_position=(self.height /2 - dp(40)), t='out_elastic', d=1)
        animation &= Animation(pinpad_background_color=(Theme().get_color(Theme().BACKGROUND_SECONDARY, 1)), t='linear', d=.2)
        animation &= Animation(pinpad_opacity=1, t='linear', d=.2)
        animation.start(self)

    def touch_check(self, widget, touch):
        if self.opacity == 0:
            return False
        if widget.collide_point(*touch.pos):
            return False
        else:
            return True 