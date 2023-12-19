import sys
from kivy.graphics import Line
from util.const import GESTURE_DATABASE
from kivy.uix.widget import Widget
from util.helpers import simplegesture

class GestureWidget(Widget):

    def __init__(self, **kwargs):
        super(GestureWidget, self).__init__(**kwargs)
        self.on_gesture = lambda _: ()
        self.on_click = lambda _: ()
        # check if OS has touch screen
        if self.is_touch_screen():
            self.bind(on_touch_down=lambda _, touch:self.touch_down(touch))
            self.bind(on_touch_up=lambda _, touch:self.touch_up(touch))
            self.bind(on_touch_move=lambda _, touch:self.touch_move(touch))


    def is_touch_screen(self):
        # for now, we'll just return true if the OS is linux
        is_linux = sys.platform.startswith('linux')
        return is_linux

    def touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return
        userdata = touch.ud
        userdata['line'] = Line(points=(touch.x, touch.y))
        return False 

    def touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return
        g = simplegesture('', list(zip(touch.ud['line'].points[::2], touch.ud['line'].points[1::2])))
        g2 = GESTURE_DATABASE.find(g, minscore=0.70)
        # print(GESTURE_DATABASE.gesture_to_str(g))
        if g2:
            self.on_gesture(g2[1])
        else:
            self.on_click()

    def touch_move(self, touch):
        if not self.collide_point(*touch.pos):
            return
        try:
            touch.ud['line'].points += [touch.x, touch.y]
            return False 
        except (KeyError) as e:
            pass
