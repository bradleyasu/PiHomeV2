from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,BooleanProperty, NumericProperty, ListProperty

from interface.pihomescreen import PiHomeScreen
from util.tools import hex
from kivy.animation import Animation
from kivy.graphics import Line, Rectangle, Ellipse, Color

Builder.load_file("./screens/WhiteBoard/whiteboard.kv")

class WhiteBoard(PiHomeScreen):
    def __init__(self, **kwargs):
        super(WhiteBoard, self).__init__(**kwargs)
        with self.canvas:
            Color(1, 1, 1, 1)
            self.rect = Rectangle(size=self.size,
                                  pos=self.pos)

        self.bind(pos=self.update_rectangle,
                  size=self.update_rectangle)


    def on_enter(self, *args):
        super().on_pre_enter(*args)
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 1)
            self.rect = Rectangle(size=self.size,
                                  pos=self.pos)

    def update_rectangle(self, instance, value):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_touch_down(self, touch):
        super(WhiteBoard, self).on_touch_down(touch)
        with self.canvas:
            Color(0,0,0)
            self.line = Line(points=[touch.pos[0], touch.pos[1]], width=2)

    def on_touch_move(self, touch):
        self.line.points = self.line.points + [touch.pos[0], touch.pos[1]]

