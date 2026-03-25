from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from components.Button.circlebutton import CircleButton
from theme.color import Color
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from util.configuration import CONFIG
from util.tools import hex
from kivy.uix.widget import Widget

Builder.load_file("./composites/PinPad/pinpad.kv")

class PinPad(Widget):
    background_color = ColorProperty((0,0,0,0))
    pinpad_background_color = ColorProperty(Theme().get_color(Theme().BACKGROUND_SECONDARY, 0))
    pinpad_button_color = ColorProperty(Theme().get_color(Theme().BUTTON_PRIMARY))
    pinpad_opacity = NumericProperty(0)
    y_position = NumericProperty(0)
    code = StringProperty()

    dot_empty_color  = ColorProperty([1, 1, 1, 0.25])
    dot_filled_color = ColorProperty(Theme().get_color(Theme().BUTTON_PRIMARY))

    pin_one   = NumericProperty(0)
    pin_two   = NumericProperty(0)
    pin_three = NumericProperty(0)
    pin_four  = NumericProperty(0)

    _dot_x_offset = NumericProperty(0)  # for shake animation

    def __init__(self, on_enter=lambda _: print('enter'), **kwargs):
        super(PinPad, self).__init__(**kwargs)
        self.pin = CONFIG.get('security', 'pin', '')
        self.on_enter = on_enter
        self.opacity = 0

        app_size = App.get_running_app().get_size()
        self.ids.pin_pad_float_container.size = app_size
        pin_grid = self.ids.pin_pad_layout
        pin_grid.bind(on_touch_down=lambda x, y: self.touch_check(x, y))

        accent = self.pinpad_button_color

        for i in range(9):
            button = CircleButton(text=str(i + 1), size=(dp(50), dp(50)))
            button.stroke_color = accent
            button.text_color = accent
            button.bind(on_release=lambda x: self.update_code(x.text))
            pin_grid.add_widget(button)

        # DELETE button — backspace symbol
        delete_btn = CircleButton(text='⌫', size=(dp(50), dp(50)))
        delete_btn.font_size = '22sp'
        delete_btn.custom_font = 'ArialUnicode'
        delete_btn.stroke_color = [0, 0, 0, 0]
        delete_btn.text_color = list(accent[:3]) + [0.6]
        delete_btn.bind(on_release=self.backspace)
        pin_grid.add_widget(delete_btn)

        # Zero
        zero_btn = CircleButton(text='0', size=(dp(50), dp(50)))
        zero_btn.stroke_color = accent
        zero_btn.text_color = accent
        zero_btn.bind(on_release=lambda x: self.update_code(x.text))
        pin_grid.add_widget(zero_btn)

        # UNLOCK button — checkmark symbol
        unlock_btn = CircleButton(text='✓', size=(dp(50), dp(50)))
        unlock_btn.font_size = '26sp'
        unlock_btn.custom_font = 'ArialUnicode'
        unlock_btn.stroke_color = accent
        unlock_btn.text_color = accent
        unlock_btn.bind(on_release=self.verify_pin)
        pin_grid.add_widget(unlock_btn)

        self.reset()

    def verify_pin(self, *args):
        if self.code == self.pin:
            self.on_enter()
            self.hide()
        else:
            self._shake_wrong_pin()

    def _shake_wrong_pin(self):
        """Shake the dots and clear the code on wrong PIN."""
        original_x = 0
        # Quick horizontal shake: right → left → right → left → center
        shake = (
            Animation(_dot_x_offset=dp(12), t='out_quad', d=0.06)
            + Animation(_dot_x_offset=-dp(10), t='out_quad', d=0.06)
            + Animation(_dot_x_offset=dp(8), t='out_quad', d=0.06)
            + Animation(_dot_x_offset=-dp(6), t='out_quad', d=0.05)
            + Animation(_dot_x_offset=dp(3), t='out_quad', d=0.05)
            + Animation(_dot_x_offset=0, t='out_quad', d=0.05)
        )

        def _on_shake_done(*args):
            self.code = ""
            self.refresh_pins()

        shake.bind(on_complete=_on_shake_done)
        shake.start(self)

    def backspace(self, *args):
        self.code = self.code[:-1]
        self.refresh_pins()

    def update_code(self, ch):
        self.code = self.code + ch
        if len(self.code) > 4:
            self.verify_pin()
        self.refresh_pins()

    def refresh_pins(self):
        self.pin_one = 360 if len(self.code) > 0 else 0
        self.pin_two = 360 if len(self.code) > 1 else 0
        self.pin_three = 360 if len(self.code) > 2 else 0
        self.pin_four = 360 if len(self.code) > 3 else 0

    def reset(self):
        self.code = ""
        self.refresh_pins()
        self.background_color = (0,0,0,0)
        self.pinpad_background_color = Theme().get_color(Theme().BACKGROUND_SECONDARY, 0)
        self.pinpad_opacity = 0
        # Start card above the visible window
        self.y_position = Window.height + dp(100)


    def show(self):
        self.reset()
        self.opacity = 1

        card_h = dp(405)
        target_y = (Window.height - card_h) / 2

        # Scrim fades in first, then card slides down smoothly
        scrim = Animation(background_color=(0, 0, 0, 0.6), t='linear', d=0.2)
        scrim &= Animation(
            pinpad_background_color=Theme().get_color(Theme().BACKGROUND_SECONDARY, 1),
            t='linear', d=0.2
        )
        slide = Animation(y_position=target_y, t='out_cubic', d=0.4)
        slide &= Animation(pinpad_opacity=1, t='linear', d=0.3)

        anim = scrim + slide
        anim.start(self)

    def hide(self):
        card_h = dp(405)
        # Slide card down off screen and fade out
        slide_out = Animation(
            y_position=-card_h - dp(20),
            pinpad_opacity=0,
            t='in_cubic', d=0.3
        )
        fade_scrim = Animation(background_color=(0, 0, 0, 0), t='linear', d=0.2)
        anim = slide_out + fade_scrim

        def _on_complete(*args):
            self.opacity = 0
            if self.parent:
                self.parent.remove_widget(self)

        anim.bind(on_complete=_on_complete)
        anim.start(self)

    def touch_check(self, widget, touch):
        if self.opacity == 0:
            return False
        if widget.collide_point(*touch.pos):
            return False
        else:
            return True 