from kivy.uix.screenmanager import Screen
from kivy.graphics import Line
from util.const import GESTURE_DATABASE
from util.helpers import goto_screen, simplegesture

class PiHomeScreen(Screen):

    def __init__(self, icon = "https://cdn.pihome.io/assets/default_app_icon.png", label = "PiHome App", is_hidden = False, requires_pin = False, **kwargs):
        super(PiHomeScreen, self).__init__(**kwargs)
        self.icon = icon
        self.label = label
        self.is_hidden = is_hidden 
        self.requires_pin = requires_pin
        self.on_gesture = lambda _: ()


    def on_touch_down(self, touch):
        userdata = touch.ud
        userdata['line'] = Line(points=(touch.x, touch.y))
        return False 

    def on_touch_up(self, touch):
        g = simplegesture('', list(zip(touch.ud['line'].points[::2], touch.ud['line'].points[1::2])))
        g2 = GESTURE_DATABASE.find(g, minscore=0.70)
        # print(GESTURE_DATABASE.gesture_to_str(g))
        if g2:
            self.on_gesture(g2[1])

    def on_touch_move(self, touch):
        try:
            touch.ud['line'].points += [touch.x, touch.y]
            return False 
        except (KeyError) as e:
            pass
