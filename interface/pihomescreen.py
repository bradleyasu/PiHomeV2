from kivy.uix.screenmanager import Screen
from kivy.graphics import Line
from kivy.properties import BooleanProperty
from system.brightness import get_brightness, set_brightness
from util.const import GESTURE_DATABASE, GESTURE_SWIPE_DOWN, GESTURE_SWIPE_DOWN_FROM_TOP
from util.helpers import get_app, simplegesture

class PiHomeScreen(Screen):

    # Locked screens can't be navigated away from.
    locked = BooleanProperty(False)

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

    def on_locked(self, instance, value):
        """Disable/enable the hamburger menu when screen lock state changes."""
        try:
            btn = get_app().menu_button
            if value:
                btn.disable()
            else:
                btn.enable()
        except Exception:
            pass

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
                ('bg_color',      th.BACKGROUND_PRIMARY),
                ('header_color',  th.BACKGROUND_SECONDARY),
                ('surface_color', th.BACKGROUND_SURFACE),
                ('border_color',  th.BACKGROUND_BORDER),
                ('text_color',    th.TEXT_PRIMARY),
                ('muted_color',   th.TEXT_SECONDARY),
                ('accent_color',  th.ACCENT_PRIMARY),
                ('status_color',  th.TEXT_SECONDARY),
            ]
            for prop, token in _standard:
                if hasattr(self, prop):
                    setattr(self, prop, th.get_color(token))
            # Elevation now uses explicit surface/border tokens (mode-correct in
            # both light and dark) instead of multiplying the header color, which
            # only elevated correctly on dark backgrounds.
            surface = th.get_color(th.BACKGROUND_SURFACE)
            border  = th.get_color(th.BACKGROUND_BORDER)
            if hasattr(self, 'card_color'):
                self.card_color = (surface[0], surface[1], surface[2], 1.0)
            if hasattr(self, 'sidebar_color'):
                self.sidebar_color = th.get_color(th.BACKGROUND_SECONDARY)
            if hasattr(self, 'divider_color'):
                self.divider_color = (border[0], border[1], border[2], 1.0)
            if hasattr(self, 'row_bg_color'):
                self.row_bg_color = (surface[0], surface[1], surface[2], 0.7)
        except Exception as e:
            pass
        # Cascade the theme refresh to every descendant widget. reload_all()
        # only calls on_config_update() on screens, so persistent composites
        # (notification center, weather, timer drawer, ...) would otherwise stay
        # on their startup colors after a runtime theme change.
        try:
            for w in self.walk(restrict=True):
                if w is self:
                    continue
                try:
                    if hasattr(w, 'on_config_update'):
                        w.on_config_update(config)
                    elif hasattr(w, '_apply_theme'):
                        w._apply_theme()
                except Exception:
                    pass
        except Exception:
            pass
        self._trigger_layout()