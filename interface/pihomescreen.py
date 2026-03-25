from kivy.uix.screenmanager import Screen
from kivy.graphics import Line
from system.brightness import get_brightness, set_brightness
from util.const import GESTURE_DATABASE, GESTURE_SWIPE_DOWN, GESTURE_SWIPE_DOWN_FROM_TOP
from util.helpers import get_app, simplegesture

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

        self.size_hint = (1, 1)

        # Locked screens can't be navigated away from.  Logic with in the screen implementation can take advantage of this
        self.locked = False

    def on_pre_leave(self, *args):
        self.manager.last_screen = self.name
        self.is_open = False
        return super().on_pre_leave(*args)

    def on_enter(self, *args):
        self.is_open = True
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
        userdata['start_y'] = touch.y
        return False

    def touch_up(self, touch):
        if 'line' not in touch.ud:
            return False
        g = simplegesture('', list(zip(touch.ud['line'].points[::2], touch.ud['line'].points[1::2])))
        g2 = GESTURE_DATABASE.find(g, minscore=0.70)
        # print(GESTURE_DATABASE.gesture_to_str(g))
        if g2:
            matched = g2[1]
            if matched == GESTURE_SWIPE_DOWN:
                start_y = touch.ud.get('start_y', 0)
                if start_y >= self.height * 0.95:
                    self.on_gesture(GESTURE_SWIPE_DOWN_FROM_TOP)
                    return False
            self.on_gesture(matched)
        return False

    def touch_move(self, touch):
        try:
            touch.ud['line'].points += [touch.x, touch.y]
            return False 
        except (KeyError) as e:
            pass

    def on_rotary_pressed(self):
        return False
    
    def on_rotary_down(self):
        return False

    def on_rotary_long_pressed(self):
        return False

    def on_rotary_turn(self, direction, button_pressed):
        return False

    def on_config_update(self, config):
        """Called by reload_all() after any settings change.
        Re-applies standard theme colors to this screen so dark/light mode
        and accent changes are reflected without a full app restart.
        """
        try:
            from theme.theme import Theme
            th = Theme()
            _standard = [
                ('bg_color',     th.BACKGROUND_PRIMARY),
                ('header_color', th.BACKGROUND_SECONDARY),
                ('text_color',   th.TEXT_PRIMARY),
                ('muted_color',  th.TEXT_SECONDARY),
                ('accent_color', th.ALERT_INFO),
                ('status_color', th.TEXT_SECONDARY),
            ]
            for prop, token in _standard:
                if hasattr(self, prop):
                    setattr(self, prop, th.get_color(token))
            # card_color is conventionally derived from header_color
            if hasattr(self, 'card_color') and hasattr(self, 'header_color'):
                hc = self.header_color
                self.card_color = (hc[0], hc[1], hc[2], 0.85)
            # sidebar / divider variants used in Settings screen
            if hasattr(self, 'sidebar_color') and hasattr(self, 'header_color'):
                hc = self.header_color
                self.sidebar_color = (hc[0] * 0.80, hc[1] * 0.80, hc[2] * 0.80, 1.0)
            if hasattr(self, 'divider_color') and hasattr(self, 'header_color'):
                hc = self.header_color
                self.divider_color = (hc[0] * 0.60, hc[1] * 0.60, hc[2] * 0.60, 1.0)
            if hasattr(self, 'row_bg_color') and hasattr(self, 'header_color'):
                hc = self.header_color
                self.row_bg_color = (hc[0], hc[1], hc[2], 0.7)
        except Exception as e:
            pass
        self._trigger_layout()