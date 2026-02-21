from kivy.uix.screenmanager import Screen
from kivy.graphics import Line
from services.audio.audioplayernew import AUDIO_PLAYER
from system.brightness import get_brightness, set_brightness
from util.const import GESTURE_DATABASE
from util.helpers import get_app, simplegesture
from util.phlog import PIHOME_LOGGER

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
        self.is_open = False
        self.disable_rotary_press_animation = False
        
        # Ensure screen fills the screen manager
        self.size_hint = (1, 1)

        # Locked screens can't be navigated away from.  Logic with in the screen implementation can take advantage of this
        self.locked = False

    def on_pre_leave(self, *args):
        self.manager.last_screen = self.name
        self.is_open = False
        return super().on_pre_leave(*args)

    def on_parent(self, widget, parent):
        # When added to screen manager, ensure we match its size
        if parent and self.size_hint == (1, 1):
            self.size = parent.size
            # Bind to parent size changes
            parent.bind(size=self._update_size_from_parent)
        return super().on_parent(widget, parent)
    
    def _update_size_from_parent(self, instance, value):
        """Update size when parent (ScreenManager) size changes"""
        if self.size_hint == (1, 1):
            self.size = value
            PIHOME_LOGGER.info(f"Screen {self.name} size updated to: {self.size}")

    def on_enter(self, *args):
        self.is_open = True
        # Force update size from parent when entering
        if self.manager and self.size_hint == (1, 1):
            self.size = self.manager.size
        PIHOME_LOGGER.info(f"PiHomeScreen.on_enter() - Screen: {self.name}, Size: {self.size}, Pos: {self.pos}")
        return super().on_enter(*args)

    def show(self):
        if self.manager is None:
            return
        self.manager.current = self.name

    def go_back(self):
        if self.manager is None:
            return
        if self.manager.last_screen:
            self.manager.current = self.manager.last_screen

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
        AUDIO_PLAYER.toggle_play()
        return False
    
    def on_rotary_down(self):
        return False

    def on_rotary_long_pressed(self):
        AUDIO_PLAYER.stop()
        AUDIO_PLAYER.clear_playlist()
        return False

    def on_rotary_turn(self, direction, button_pressed):
        if direction == 1:
            AUDIO_PLAYER.volume_up()
        elif direction == -1:
            AUDIO_PLAYER.volume_down()
        return False

    def on_config_update(self, payload):
        # default behavior is simply to reload the screen
        self._trigger_layout()