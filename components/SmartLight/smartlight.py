from kivy.app import App
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.graphics import Color, Ellipse, Line
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.gesture import Gesture, GestureDatabase

Builder.load_file("./components/SmartLight/smartlight.kv")


class SmartLight(Widget):

    degrees = NumericProperty(0)

    def __init__(self, **kwargs):
       super(SmartLight, self).__init__(**kwargs)
       self.is_adjusting = False
       self.last_x = -1
       self.last_y = -1
       self.x_loc = '' # LEFT | RIGHT
       self.y_loc = '' # TOP | BOTTOM
       self.status = 'neutral'
       self.degrees = 0

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.last_x = touch.x
            self.last_y = touch.y
            if touch.x > self.width / 2:
                self.x_loc = 'RIGHT'
            else:
                self.x_loc = 'LEFT'
            if touch.y > self.height / 2:
                self.y_loc = 'TOP'
            else:
                self.y_loc = 'BOTTOM'
            self.is_adjusting = True
            return False
        else:
            return super(SmartLight, self).on_touch_down(touch)


    def on_touch_move(self, touch):
        self.x_dir = ""
        self.y_dir = ""
        if self.is_adjusting:
            if touch.x > self.last_x:
                self.x_dir = "right"
            elif touch.x < self.last_x:
                self.x_dir = "left"
            else:
                pass

            if touch.y > self.last_y:
                self.y_dir = "up"
            elif touch.y < self.last_y:
                self.y_dir = "down"
            else:
                pass


            if self.y_loc == 'TOP' and self.x_dir == 'right' and self.status == 'neutral':
                self.status = 'increase'
            elif self.y_loc == 'TOP' and self.x_dir == 'left' and self.status == 'neutral':
                self.status = 'decrease'
            elif self.y_loc == 'BOTTOM' and self.x_dir == 'right' and self.status == 'neutral':
                self.status = 'decrease'
            elif self.y_loc == 'BOTTOM' and self.x_dir == 'left' and self.status == 'neutral':
                self.status = 'increase'


            print(self.status)

            if(self.status == 'decrease'):
                self.degrees = self.degrees + 1
                if self.degrees >= 360:
                    self.degrees = 0
            elif(self.status == 'increase'):
                self.degrees = self.degrees - 1
                if self.degrees < 0:
                    self.degrees = 359

            self.last_x = touch.x
            self.last_y = touch.y
        return True

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            self.is_adjusting = False
            self.status = 'neutral'
            return False
        else:
            return super(SmartLight, self).on_touch_up(touch)


