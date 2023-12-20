from kivy.uix.screenmanager import Screen
from kivy.graphics import Line
from system.rotary import ROTARY_ENCODER
from util.const import GESTURE_DATABASE
from util.helpers import audio_player, get_app, info, simplegesture, warn

class PiHomeScreen(Screen):

    rotary_encoder = None

    def __init__(self, icon = "https://cdn.pihome.io/assets/default_app_icon.png", label = "PiHome App", is_hidden = False, requires_pin = False, **kwargs):
        super(PiHomeScreen, self).__init__(**kwargs)
        self.rotary_encoder = ROTARY_ENCODER
        self.icon = icon
        self.label = label
        self.is_hidden = is_hidden 
        self.requires_pin = requires_pin
        self.on_gesture = lambda _: ()
        self.bind(on_touch_down=lambda _, touch:self.touch_down(touch))
        self.bind(on_touch_up=lambda _, touch:self.touch_up(touch))
        self.bind(on_touch_move=lambda _, touch:self.touch_move(touch))

        if self.rotary_encoder.is_initialized:
            self.rotary_encoder.button_callback = lambda _: self.rotary_pressed()
            self.rotary_encoder.update_callback = lambda direction: self.rotary_handler(direction)
            info("Rotary Encoder Initialized: {}".format(self.label))
        else: 
            info("Rotary Encoder Not Initialized: {}".format(self.label))
            warn("Rotary Encoder Instance State: ".format(self.rotary_encoder.is_initialized))
        info("PiHomeScreen Initialized: {} and hidden state set to {}".format(self.label, self.is_hidden))


    def touch_down(self, touch):
        userdata = touch.ud
        userdata['line'] = Line(points=(touch.x, touch.y))
        return False

    def touch_up(self, touch):
        g = simplegesture('', list(zip(touch.ud['line'].points[::2], touch.ud['line'].points[1::2])))
        g2 = GESTURE_DATABASE.find(g, minscore=0.70)
        # print(GESTURE_DATABASE.gesture_to_str(g))
        if g2:
            self.on_gesture(g2[1])
        return False

    def touch_move(self, touch):
        try:
            touch.ud['line'].points += [touch.x, touch.y]
            return False 
        except (KeyError) as e:
            pass

    def rotary_handler(self, direction):
        if direction == 1:
            audio_player().volume_up()
        elif direction == -1:
            audio_player().volume_down()
        return False

    def rotary_pressed(self):
        audio_player().toggle_play()
        return False
    
