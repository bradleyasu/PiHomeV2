from kivy.uix.screenmanager import Screen
from kivy.graphics import Line
from system.brightness import get_brightness, set_brightness
from util.const import GESTURE_DATABASE
from util.helpers import audio_player, get_app, info, simplegesture, warn

class PiHomeScreen(Screen):

    def __init__(self, icon = "https://cdn.pihome.io/assets/default_app_icon.png", label = "PiHome App", is_hidden = False, requires_pin = False, **kwargs):
        super(PiHomeScreen, self).__init__(**kwargs)
        self.icon = icon
        self.label = label
        self.is_hidden = is_hidden 
        self.requires_pin = requires_pin
        self.on_gesture = lambda _: ()
        self.bind(on_touch_down=lambda _, touch:self.touch_down(touch))
        self.bind(on_touch_up=lambda _, touch:self.touch_up(touch))
        self.bind(on_touch_move=lambda _, touch:self.touch_move(touch))


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

    def on_rotary_pressed(self):
        audio_player().toggle_play()
        return False

    def on_rotary_long_pressed(self):
        audio_player().stop()
        audio_player().clear_playlist()
        return False

    def on_rotary_turn(self, direction, button_pressed):
        if button_pressed:
            current_brightness = get_brightness()
            if current_brightness is None or current_brightness == 0 or current_brightness == 100:
                return False
            set_brightness(current_brightness + direction)
            return False

        if direction == 1:
            audio_player().volume_up()
        elif direction == -1:
            audio_player().volume_down()
        return False

    def on_config_update(self, payload):
        # default behavior is simply to reload the screen
        self._trigger_layout()