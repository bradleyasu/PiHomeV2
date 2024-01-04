from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import AsyncImage  
from kivy.uix.label import Label
from interface.gesturewidget import GestureWidget
from theme.theme import Theme
from kivy.properties import BooleanProperty, ColorProperty, NumericProperty, StringProperty, ListProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp

from util.helpers import get_app

Builder.load_file("./components/ArrowButton/arrowbutton.kv")

LEFT = "left"
RIGHT = "right"
UP = "up"
DOWN = "down"
VERTICAL = "vertical"
HORIZONTAL = "horizontal"

class ArrowButton(Widget):
    orientation = StringProperty(HORIZONTAL)
    direction = StringProperty(LEFT)
    color = ColorProperty((1,1,1,1))
    points = ListProperty([])

    def __init__(self, **kwargs):
        super(ArrowButton, self).__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(20), dp(20))
        self.bind(pos=self.on_position_change, size=self.on_position_change)

    def on_position_change(self, instance, value):
        self.calculate_points()

    def calculate_points(self):
        if self.orientation == HORIZONTAL:
            if self.direction == LEFT:
                self.points = [self.width / 2 + self.x, self.y + self.height, self.x + self.width, self.y + self.height / 2, self.x + self.width / 2, self.y]
            elif self.direction == RIGHT:
                self.points = [self.x + self.width / 2, self.y + self.height, self.x, self.y + self.height / 2, self.x + self.width / 2, self.y]
        elif self.orientation == VERTICAL:
            if self.direction == UP:
                self.points = [self.x, self.y + self.height /2, self.x + self.width /2, self.y + self.height, self.x + self.width, self.y + self.height /2]
            elif self.direction == DOWN:
                self.points = [self.x, self.y + self.height /2, self.x + self.width /2, self.y, self.x + self.width, self.y + self.height /2]

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.orientation == HORIZONTAL:
                if self.direction == LEFT:
                    self.direction = RIGHT
                elif self.direction == RIGHT:
                    self.direction = LEFT
            elif self.orientation == VERTICAL:
                if self.direction == UP:
                    self.direction = DOWN
                elif self.direction == DOWN:
                    self.direction = UP
            self.calculate_points()
            return super(ArrowButton, self).on_touch_down(touch)



            