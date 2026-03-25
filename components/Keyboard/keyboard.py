"""
components/Keyboard/keyboard.py

Sleek custom on-screen keyboard for PiHome touchscreen.

Usage:
    from components.Keyboard.keyboard import PiTextInput

    Replace any TextInput in .kv with PiTextInput — the keyboard appears
    automatically when the field is tapped.

    Call ensure_keyboard_attached() once at app start (e.g. in main.py build())
    to add the keyboard widget to the root Window.
"""

from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.properties import ObjectProperty, BooleanProperty
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.clock import Clock
from theme.theme import Theme
import platform

_IS_PI = platform.system() != 'Darwin'


# ── Key layout definitions ────────────────────────────────────────────────────
# Each key is (display_label, size_hint_x_weight)

_ROW_LOWER = [
    [('q',1),('w',1),('e',1),('r',1),('t',1),('y',1),('u',1),('i',1),('o',1),('p',1)],
    [('a',1),('s',1),('d',1),('f',1),('g',1),('h',1),('j',1),('k',1),('l',1)],
    [('⇧',1.5),('z',1),('x',1),('c',1),('v',1),('b',1),('n',1),('m',1),('⌫',1.5)],
    [('123',2),(',',1),('_SPACE_',4.5),('.',1),('↵',2)],
]

_ROW_UPPER = [
    [('Q',1),('W',1),('E',1),('R',1),('T',1),('Y',1),('U',1),('I',1),('O',1),('P',1)],
    [('A',1),('S',1),('D',1),('F',1),('G',1),('H',1),('J',1),('K',1),('L',1)],
    [('⇧',1.5),('Z',1),('X',1),('C',1),('V',1),('B',1),('N',1),('M',1),('⌫',1.5)],
    [('123',2),(',',1),('_SPACE_',4.5),('.',1),('↵',2)],
]

_ROW_NUM = [
    [('1',1),('2',1),('3',1),('4',1),('5',1),('6',1),('7',1),('8',1),('9',1),('0',1)],
    [('-',1),('/',1),(':',1),(';',1),('(',1),(')',1),('$',1),('&',1),('@',1),('"',1)],
    [('#',1.5),('.',1),(',',1),('?',1),('!',1),("'",1),('%',1),('=',1),('⌫',1.5)],
    [('abc',2),('_SPACE_',5.5),('↵',2)],
]

_SPECIAL = {'⇧', '⌫', '123', 'abc', '↵', '_SPACE_'}

KB_ROWS = 4


# ── _Key widget ───────────────────────────────────────────────────────────────

class _Key(BoxLayout):
    """A single pressable keyboard key drawn with canvas instructions."""

    def __init__(self, key: str, weight: float, on_press, theme: dict, **kwargs):
        super().__init__(**kwargs)
        self._key      = key
        self._on_press = on_press
        self.size_hint = (weight, 1)
        self.padding   = [dp(3), dp(3), dp(3), dp(3)]

        is_action  = (key == '↵')
        is_special = (key in _SPECIAL) and (key != '_SPACE_')

        if is_action:
            bg = theme['action']
        elif is_special:
            bg = theme['key_special']
        else:
            bg = theme['key_normal']

        with self.canvas.before:
            self._c    = Color(rgba=bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(9)])
        self.bind(pos=self._refresh, size=self._refresh)

        # Label / icon
        if key == '_SPACE_':
            child = Widget()          # blank — track bar is drawn separately
        elif key in ('⇧', '⌫'):
            child = Label(
                text=key,
                font_name='ArialUnicode', font_size='20sp',
                color=theme['fg_special'],
                halign='center', valign='middle',
            )
            child.bind(size=lambda i, v: setattr(i, 'text_size', v))
        elif key == '↵':
            child = Label(
                text='done',
                font_name='Nunito', font_size='12sp', bold=True,
                color=theme['fg_action'],
                halign='center', valign='middle',
            )
            child.bind(size=lambda i, v: setattr(i, 'text_size', v))
        elif key in ('123', 'abc'):
            child = Label(
                text=key,
                font_name='Nunito', font_size='13sp', bold=True,
                color=theme['fg_special'],
                halign='center', valign='middle',
            )
            child.bind(size=lambda i, v: setattr(i, 'text_size', v))
        else:
            child = Label(
                text=key,
                font_name='Nunito', font_size='16sp', bold=True,
                color=theme['fg_normal'],
                halign='center', valign='middle',
            )
            child.bind(size=lambda i, v: setattr(i, 'text_size', v))

        self.add_widget(child)

    def _refresh(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._on_press(self._key)
            return True
        return False


# ── PiHomeKeyboard ────────────────────────────────────────────────────────────

class PiHomeKeyboard(BoxLayout):
    """
    Slide-up on-screen keyboard.  Added once to the Window as a permanent
    overlay; call show(target_input) / hide() to control visibility.
    """

    target  = ObjectProperty(None, allownone=True)
    shifted = BooleanProperty(False)
    nums    = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Compute dp-based sizes here, not at module load time,
        # so the Pi display metrics are fully initialised first.
        kb_row_h  = dp(52)
        kb_pad    = dp(8)
        preview_h = dp(36)
        kb_height = preview_h + kb_row_h * KB_ROWS + kb_pad * 2 + dp(4) * (KB_ROWS - 1)

        self.orientation = 'vertical'
        self.size_hint   = (1, None)
        self.height      = kb_height
        self._kb_height  = kb_height
        self.y           = -kb_height   # start off-screen below
        self.opacity     = 0
        self.padding     = [dp(10), kb_pad, dp(10), 0]
        self.spacing     = dp(4)

        th = Theme()
        bg  = th.get_color(th.BACKGROUND_SECONDARY)

        def _lift(c, factor):
            return tuple(min(c[i] * factor, 1.0) for i in range(3)) + (1.0,)

        self._theme = {
            'bg':          bg,
            'key_normal':  _lift(bg, 2.2),
            'key_special': _lift(bg, 3.0),
            'action':      th.get_color(th.ALERT_INFO),
            'fg_normal':   (1.0, 1.0, 1.0, 0.92),
            'fg_special':  (1.0, 1.0, 1.0, 0.65),
            'fg_action':   (1.0, 1.0, 1.0, 1.0),
        }

        with self.canvas.before:
            Color(rgba=bg)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            # thin top separator line
            Color(rgba=(1, 1, 1, 0.07))
            self._line = Rectangle(pos=(self.x, self.top - dp(1)),
                                   size=(self.width, dp(1)))
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        # ── Text preview bar (sits above key rows) ──────────────────────
        self._preview_bar = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=preview_h,
            padding=[dp(12), dp(4), dp(12), dp(4)],
        )
        preview_bg = _lift(bg, 1.4)
        with self._preview_bar.canvas.before:
            Color(rgba=preview_bg)
            self._preview_bg_rect = RoundedRectangle(
                pos=self._preview_bar.pos,
                size=self._preview_bar.size,
                radius=[dp(6)],
            )
            # bottom separator
            Color(rgba=(1, 1, 1, 0.07))
            self._preview_sep = Rectangle(
                pos=self._preview_bar.pos,
                size=(self._preview_bar.width, dp(1)),
            )
        self._preview_bar.bind(
            pos=self._upd_preview_bg, size=self._upd_preview_bg
        )

        self._preview_label = Label(
            text='',
            font_name='Nunito',
            font_size='14sp',
            color=(1, 1, 1, 0.85),
            halign='left',
            valign='middle',
            shorten=True,
            shorten_from='left',
        )
        self._preview_label.bind(
            size=lambda i, v: setattr(i, 'text_size', v)
        )
        self._preview_hint = Label(
            text='',
            font_name='Nunito',
            font_size='11sp',
            color=(1, 1, 1, 0.30),
            halign='right',
            valign='middle',
            size_hint_x=None,
            width=dp(100),
        )
        self._preview_hint.bind(
            size=lambda i, v: setattr(i, 'text_size', v)
        )
        self._preview_bar.add_widget(self._preview_label)
        self._preview_bar.add_widget(self._preview_hint)
        self.add_widget(self._preview_bar)

        # ── Key rows container ──────────────────────────────────────────
        self._keys_container = BoxLayout(
            orientation='vertical', size_hint=(1, 1), spacing=dp(4),
        )
        self.add_widget(self._keys_container)

        self._build_rows()

    # ── private ───────────────────────────────────────────────────────────────

    def _upd_bg(self, *_):
        self._bg.pos   = self.pos
        self._bg.size  = self.size
        self._line.pos = (self.x, self.top - dp(1))
        self._line.size = (self.width, dp(1))

    def _upd_preview_bg(self, *_):
        bar = self._preview_bar
        self._preview_bg_rect.pos  = bar.pos
        self._preview_bg_rect.size = bar.size
        self._preview_sep.pos  = (bar.x, bar.y)
        self._preview_sep.size = (bar.width, dp(1))

    def _build_rows(self):
        self._keys_container.clear_widgets()
        rows = _ROW_UPPER if self.shifted else (_ROW_NUM if self.nums else _ROW_LOWER)
        for row in rows:
            total_w = sum(w for _, w in row)
            row_box = BoxLayout(orientation='horizontal', size_hint_y=1, spacing=dp(4))
            for lbl, w in row:
                key = _Key(lbl, w / total_w, self._press, self._theme)
                row_box.add_widget(key)
            self._keys_container.add_widget(row_box)

    # ── public ────────────────────────────────────────────────────────────────

    def show(self, target):
        # Unfocus the previous target so only one field is active at a time.
        # (Kivy's normal focus exclusivity relies on _bind_keyboard which
        # PiTextInput suppresses on Pi.)
        if self.target is not None and self.target is not target:
            self.target.unbind(text=self._sync_preview)
            self.target.focus = False
        self.target = target
        # Sync preview bar to the new target
        target.bind(text=self._sync_preview)
        self._sync_preview(target, target.text)
        hint = getattr(target, 'hint_text', '')
        self._preview_hint.text = hint if hint else ''
        # Re-add to Window each time so we are always the topmost widget
        if self.parent:
            self.parent.remove_widget(self)
        Window.add_widget(self)
        self.opacity = 1
        Animation.cancel_all(self, 'y')
        Animation(y=0, d=0.2, t='out_cubic').start(self)

    def hide(self):
        if self.target is not None:
            self.target.unbind(text=self._sync_preview)
        Animation.cancel_all(self, 'y')
        anim = Animation(y=-self._kb_height, d=0.18, t='in_cubic')
        anim.bind(on_complete=lambda *_: setattr(self, 'opacity', 0))
        anim.start(self)
        self._preview_label.text = ''
        self._preview_hint.text = ''
        self.target = None

    def _sync_preview(self, instance, text):
        self._preview_label.text = text

    # ── kivy property observers ───────────────────────────────────────────────

    def on_shifted(self, *_):
        self._build_rows()

    def on_nums(self, *_):
        self._build_rows()

    # ── key press handler ─────────────────────────────────────────────────────

    def _press(self, key):
        widget = self.target

        if key == '⌫':
            if widget:
                if widget.selection_text:
                    widget.delete_selection()
                else:
                    widget.do_backspace()

        elif key == '_SPACE_':
            if widget:
                widget.insert_text(' ')

        elif key == '⇧':
            self.shifted = not self.shifted
            self.nums    = False

        elif key == '123':
            self.nums    = True
            self.shifted = False

        elif key == 'abc':
            self.nums    = False
            self.shifted = False

        elif key == '↵':
            self.nums    = False
            self.shifted = False
            self.hide()
            if widget:
                widget.focus = False

        else:
            if widget:
                widget.insert_text(key)
            # auto-lower after one capital
            if self.shifted:
                self.shifted = False


# ── PiTextInput ───────────────────────────────────────────────────────────────

class PiTextInput(TextInput):
    """
    Drop-in replacement for TextInput that shows PiHomeKeyboard on focus
    on the Pi touchscreen.  On macOS the native/system keyboard is used
    normally so physical-keyboard debugging is unaffected.
    """

    _active_input = None   # class-level ref to the currently focused instance

    def _bind_keyboard(self):
        if _IS_PI:
            return   # suppress Kivy's keyboard on Pi
        super()._bind_keyboard()

    def _unbind_keyboard(self):
        if _IS_PI:
            return
        super()._unbind_keyboard()

    def on_focus(self, instance, value):
        if value:
            # Unfocus the previously active PiTextInput so only one field
            # is active at a time.  _bind_keyboard is suppressed on Pi so
            # Kivy can't enforce this for us.
            prev = PiTextInput._active_input
            if prev is not None and prev is not self and prev.focus:
                prev.focus = False
            PiTextInput._active_input = self
            if not _IS_PI:
                return   # macOS uses Kivy's native keyboard
            Clock.schedule_once(lambda dt: _get_keyboard().show(self), 0)
        else:
            if PiTextInput._active_input is self:
                PiTextInput._active_input = None
            if not _IS_PI:
                return
            Clock.schedule_once(self._maybe_hide, 0.06)

    def on_touch_up(self, touch):
        result = super().on_touch_up(touch)
        if _IS_PI and self.collide_point(*touch.pos) and self.focus:
            # Field was already focused — on_focus won't fire again,
            # so show the keyboard explicitly on each tap.
            Clock.schedule_once(lambda dt: _get_keyboard().show(self), 0)
        return result

    def _maybe_hide(self, dt):
        kb = _get_keyboard()
        if kb.target is self:
            kb.hide()


# ── Singleton management ──────────────────────────────────────────────────────

_keyboard_instance: PiHomeKeyboard = None


def _get_keyboard() -> PiHomeKeyboard:
    global _keyboard_instance
    if _keyboard_instance is None:
        _keyboard_instance = PiHomeKeyboard()
        # Defer adding to Window until after the current frame so that
        # build() has returned its root widget first (z-order matters).
        Clock.schedule_once(lambda dt: Window.add_widget(_keyboard_instance), 0)
    return _keyboard_instance


def ensure_keyboard_attached():
    """
    No-op kept for API compatibility — lazy creation on first show() is
    sufficient and avoids z-order / dp-metric issues at startup.
    """
    pass
