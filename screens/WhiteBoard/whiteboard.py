"""Redesigned WhiteBoard — a sleek doodle/painting canvas.

Features
--------
- Full-screen dark drawing surface
- Stroke list with undo support
- Floating bottom toolbar:
    - 7-colour palette with active ring indicator
    - 4 brush sizes with dot preview
    - Eraser (paints in bg colour)
    - Undo (removes last stroke)
    - Clear (wipes canvas with a quick animation)
"""

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import (
    Color as KColor,
    Ellipse,
    Line,
    Rectangle,
    RoundedRectangle,
)
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from interface.pihomescreen import PiHomeScreen

Builder.load_file("./screens/WhiteBoard/whiteboard.kv")

# ── Design tokens ─────────────────────────────────────────────────────────────

_CANVAS_BG   = [0.07, 0.07, 0.09, 1.0]
_TOOLBAR_BG  = [0.13, 0.13, 0.18, 1.0]
_DIVIDER_CLR = [1.0, 1.0, 1.0, 0.08]

_PALETTE = [
    [1.00, 1.00, 1.00, 1.0],   # White
    [1.00, 0.42, 0.42, 1.0],   # Coral
    [1.00, 0.85, 0.24, 1.0],   # Amber
    [0.42, 0.80, 0.48, 1.0],   # Mint
    [0.30, 0.59, 1.00, 1.0],   # Blue
    [0.78, 0.48, 1.00, 1.0],   # Lavender
    [1.00, 0.62, 0.11, 1.0],   # Orange
]

_SIZES     = [dp(2), dp(5), dp(10), dp(20)]
_DOT_RADII = [dp(2), dp(4), dp(7),  dp(11)]   # visual dot for each size step

_TOOLBAR_H = dp(68)
_TOOLBAR_R = dp(20)   # top-corner radius

# ── DrawingCanvas ─────────────────────────────────────────────────────────────

class DrawingCanvas(Widget):
    """Full-screen widget that captures touch and renders freehand strokes.

    Each stroke is stored as (r, g, b, a, width, [x0, y0, x1, y1, ...]) so
    that undo can pop the last entry and redraw from scratch cleanly.
    """

    brush_color = ListProperty([1.0, 1.0, 1.0, 1.0])
    brush_width = NumericProperty(dp(5))
    erase_mode  = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._strokes: list = []            # (r,g,b,a, width, [pts])
        self._active_stroke: list | None = None
        self._active_line = None

        self.bind(pos=self._draw_bg, size=self._draw_bg)
        Clock.schedule_once(lambda dt: self._draw_bg(), 0)

    def _draw_bg(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            KColor(rgba=_CANVAS_BG)
            Rectangle(pos=self.pos, size=self.size)

    # ── Touch ─────────────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        touch.grab(self)
        if self.erase_mode:
            r, g, b, a = _CANVAS_BG[0], _CANVAS_BG[1], _CANVAS_BG[2], 1.0
            w = self.brush_width * 2.8
        else:
            r, g, b, a = self.brush_color
            w = self.brush_width
        pts = [touch.x, touch.y]
        self._active_stroke = pts
        self._strokes.append((r, g, b, a, w, pts))
        with self.canvas:
            KColor(r, g, b, a)
            self._active_line = Line(
                points=pts[:], width=w, cap="round", joint="round",
            )
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False
        if self._active_stroke is not None:
            self._active_stroke += [touch.x, touch.y]
            self._active_line.points = self._active_stroke[:]
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        self._active_stroke = None
        self._active_line   = None
        return True

    # ── Operations ────────────────────────────────────────────────────────────

    def undo(self):
        if not self._strokes:
            return
        self._strokes.pop()
        self._redraw_all()

    def clear_canvas(self, animate=True):
        if animate:
            a = Animation(opacity=0, duration=0.15)
            a.bind(on_complete=lambda *_: self._do_clear())
            a.start(self)
        else:
            self._do_clear()

    def _do_clear(self):
        self._strokes.clear()
        self.canvas.clear()
        self._draw_bg()
        self.opacity = 1.0

    def _redraw_all(self):
        self.canvas.clear()
        self._draw_bg()
        with self.canvas:
            for r, g, b, a, w, pts in self._strokes:
                KColor(r, g, b, a)
                Line(points=pts[:], width=w, cap="round", joint="round")


# ── ColorSwatch ───────────────────────────────────────────────────────────────

class ColorSwatch(Widget):
    """Filled circle swatch; shows a soft outer ring when selected."""

    swatch_color = ListProperty([1, 1, 1, 1])
    selected     = BooleanProperty(False)
    on_pressed   = ObjectProperty(None)

    _D = dp(22)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(34), dp(34))
        self.pos_hint = {'center_y': 0.5}
        self.bind(
            pos=self._draw, size=self._draw,
            swatch_color=self._draw, selected=self._draw,
        )
        Clock.schedule_once(lambda dt: self._draw(), 0)

    def _draw(self, *_):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        d = self._D
        with self.canvas:
            if self.selected:
                KColor(rgba=[1, 1, 1, 0.28])
                Ellipse(
                    pos=(cx - d / 2 - dp(5), cy - d / 2 - dp(5)),
                    size=(d + dp(10), d + dp(10)),
                )
            KColor(rgba=self.swatch_color)
            Ellipse(pos=(cx - d / 2, cy - d / 2), size=(d, d))

    def on_touch_down(self, touch):
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self.on_pressed:
            self.on_pressed()
            return True
        return False


# ── BrushSizeBtn ──────────────────────────────────────────────────────────────

class BrushSizeBtn(Widget):
    """Dot showing a brush size; subtle circle bg when selected."""

    dot_radius = NumericProperty(dp(3))
    dot_color  = ListProperty([1, 1, 1, 1])
    selected   = BooleanProperty(False)
    on_pressed = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(32), dp(32))
        self.pos_hint = {'center_y': 0.5}
        self.bind(
            pos=self._draw, size=self._draw,
            dot_radius=self._draw, dot_color=self._draw, selected=self._draw,
        )
        Clock.schedule_once(lambda dt: self._draw(), 0)

    def _draw(self, *_):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        r = min(self.dot_radius, dp(12))
        with self.canvas:
            if self.selected:
                KColor(rgba=[1, 1, 1, 0.13])
                Ellipse(
                    pos=(cx - dp(14), cy - dp(14)),
                    size=(dp(28), dp(28)),
                )
            KColor(rgba=self.dot_color)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))

    def on_touch_down(self, touch):
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self.on_pressed:
            self.on_pressed()
            return True
        return False


# ── IconBtn ───────────────────────────────────────────────────────────────────

class IconBtn(Widget):
    """Material-icon touch button with optional active-state highlight."""

    icon       = StringProperty("\ue166")
    tint       = ListProperty([1, 1, 1, 0.50])
    selected   = BooleanProperty(False)
    on_pressed = ObjectProperty(None)

    _S = dp(36)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (self._S, self._S)
        self.pos_hint = {'center_y': 0.5}

        self._lbl = Label(
            text=self.icon,
            font_name="MaterialIcons",
            font_size="21sp",
            halign="center",
            valign="middle",
        )
        self._lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.bind(
            icon=lambda _, v: setattr(self._lbl, "text", v),
            tint=self._sync,
            selected=self._sync,
            pos=self._sync_pos,
            size=self._sync_pos,
        )
        self.add_widget(self._lbl)
        Clock.schedule_once(lambda dt: self._sync_pos(), 0)

    def _sync_pos(self, *_):
        self._lbl.pos  = self.pos
        self._lbl.size = self.size
        self._sync()

    def _sync(self, *_):
        self.canvas.before.clear()
        if self.selected:
            with self.canvas.before:
                KColor(rgba=[1, 1, 1, 0.13])
                Ellipse(pos=self.pos, size=self.size)
        self._lbl.color = [1, 1, 1, 0.92] if self.selected else list(self.tint)

    def on_touch_down(self, touch):
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self.on_pressed:
            self.on_pressed()
            return True
        return False


# ── Toolbar ───────────────────────────────────────────────────────────────────

class Toolbar(BoxLayout):
    """Opaque tray that consumes all touches within its bounds so the
    drawing canvas never receives touches in the toolbar region."""

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            super().on_touch_down(touch)
            return True
        return False

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            super().on_touch_move(touch)
            return True
        return False

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            super().on_touch_up(touch)
            return True
        return False


# ── WhiteBoard ────────────────────────────────────────────────────────────────

class WhiteBoard(PiHomeScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._color_idx = 0
        self._size_idx  = 1   # default: medium-small

        self._canvas_widget: DrawingCanvas | None = None
        self._swatches:  list[ColorSwatch]  = []
        self._size_btns: list[BrushSizeBtn] = []
        self._erase_btn: IconBtn | None     = None

        Clock.schedule_once(self._build_ui, 0)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self, *_):
        self.clear_widgets()
        root = FloatLayout()

        # Drawing canvas (full screen) ─────────────────────────────────────────
        dc = DrawingCanvas(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        dc.brush_color = list(_PALETTE[self._color_idx])
        dc.brush_width = _SIZES[self._size_idx]
        self._canvas_widget = dc
        root.add_widget(dc)

        # Toolbar ──────────────────────────────────────────────────────────────
        toolbar = Toolbar(
            orientation="horizontal",
            spacing=dp(4),
            padding=[dp(16), 0, dp(16), 0],
            size_hint=(1, None),
            height=_TOOLBAR_H,
            pos_hint={"x": 0, "y": 0},
        )

        def _bg(*_):
            toolbar.canvas.before.clear()
            with toolbar.canvas.before:
                KColor(rgba=_TOOLBAR_BG)
                RoundedRectangle(
                    pos=toolbar.pos,
                    size=toolbar.size,
                    radius=[_TOOLBAR_R],
                )

        toolbar.bind(pos=_bg, size=_bg)
        Clock.schedule_once(lambda dt: _bg(), 0)

        # Colour palette ───────────────────────────────────────────────────────
        self._swatches = []
        for i, clr in enumerate(_PALETTE):
            sw = ColorSwatch(swatch_color=list(clr), selected=(i == self._color_idx))
            sw.on_pressed = (lambda idx=i: lambda: self._on_color(idx))()
            self._swatches.append(sw)
            toolbar.add_widget(sw)

        toolbar.add_widget(_divider())

        # Brush sizes ──────────────────────────────────────────────────────────
        self._size_btns = []
        for i, (sz, dr) in enumerate(zip(_SIZES, _DOT_RADII)):
            btn = BrushSizeBtn(
                dot_radius=dr,
                dot_color=list(_PALETTE[self._color_idx]),
                selected=(i == self._size_idx),
            )
            btn.on_pressed = (lambda idx=i: lambda: self._on_size(idx))()
            self._size_btns.append(btn)
            toolbar.add_widget(btn)

        toolbar.add_widget(_divider())

        # Eraser ───────────────────────────────────────────────────────────────
        erase_btn = IconBtn(icon="\ue265")   # format_color_reset = eraser
        erase_btn.on_pressed = self._on_eraser
        self._erase_btn = erase_btn
        toolbar.add_widget(erase_btn)

        # Flexible spacer centres the right-side actions ───────────────────────
        toolbar.add_widget(Widget())

        # Undo ─────────────────────────────────────────────────────────────────
        undo_btn = IconBtn(icon="\ue166")    # undo
        undo_btn.on_pressed = self._on_undo
        toolbar.add_widget(undo_btn)

        # Clear / trash ────────────────────────────────────────────────────────
        clear_btn = IconBtn(icon="\ue872", tint=[1.0, 0.38, 0.38, 0.80])
        clear_btn.on_pressed = self._on_clear
        toolbar.add_widget(clear_btn)

        root.add_widget(toolbar)
        self.add_widget(root)

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_color(self, idx: int):
        self._color_idx = idx
        if self._erase_btn:
            self._erase_btn.selected = False
        for i, sw in enumerate(self._swatches):
            sw.selected = (i == idx)
        for btn in self._size_btns:
            btn.dot_color = list(_PALETTE[idx])
        if self._canvas_widget:
            self._canvas_widget.brush_color = list(_PALETTE[idx])
            self._canvas_widget.erase_mode  = False

    def _on_size(self, idx: int):
        self._size_idx = idx
        for i, btn in enumerate(self._size_btns):
            btn.selected = (i == idx)
        if self._canvas_widget:
            self._canvas_widget.brush_width = _SIZES[idx]

    def _on_eraser(self):
        active = not (self._erase_btn.selected if self._erase_btn else False)
        if self._erase_btn:
            self._erase_btn.selected = active
        if self._canvas_widget:
            self._canvas_widget.erase_mode = active

    def _on_undo(self):
        if self._canvas_widget:
            self._canvas_widget.undo()

    def _on_clear(self):
        if self._canvas_widget:
            self._canvas_widget.clear_canvas(animate=True)

    # ── Screen lifecycle ──────────────────────────────────────────────────────

    def on_enter(self, *args):
        # Preserve drawing across screen transitions — no clear on re-enter
        super().on_enter(*args)

    def on_leave(self, *args):
        return super().on_leave(*args)


# ── Helper ────────────────────────────────────────────────────────────────────

def _divider() -> Widget:
    d = Widget(size_hint=(None, 1), width=dp(1))

    def _draw(*_):
        d.canvas.clear()
        with d.canvas:
            KColor(rgba=_DIVIDER_CLR)
            Rectangle(
                pos=(d.x, d.y + dp(16)),
                size=(dp(1), d.height - dp(32)),
            )

    d.bind(pos=_draw, size=_draw)
    Clock.schedule_once(lambda dt: _draw(), 0)
    return d

