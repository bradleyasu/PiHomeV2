from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color as KColor, Rectangle
from kivy.metrics import dp, sp
from kivy.properties import ColorProperty, ListProperty
from kivy.uix.widget import Widget
from theme.theme import Theme


class BarChart(Widget):
    """Lightweight daily-bar chart drawn entirely on the canvas.

    Pi-safe: only redraws when ``data``/``labels`` change or on resize, never
    per-frame. Text is rendered to textures via CoreLabel and blitted once.
    """

    data   = ListProperty([])   # list of floats (kWh per day)
    labels = ListProperty([])   # list of short x-axis date strings, same length as data

    bar_color   = ColorProperty(Theme().get_color(Theme().ACCENT_PRIMARY))
    axis_color  = ColorProperty([1, 1, 1, 0.18])
    label_color = ColorProperty([1, 1, 1, 0.45])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            pos=self._redraw, size=self._redraw,
            data=self._redraw, labels=self._redraw,
            bar_color=self._redraw, axis_color=self._redraw, label_color=self._redraw,
        )

    def _text(self, text, x, y, size, color, anchor_x="left"):
        lbl = CoreLabel(text=text, font_size=size, font_name="Nunito")
        lbl.refresh()
        tex = lbl.texture
        tx = x - tex.width if anchor_x == "right" else (
            x - tex.width / 2 if anchor_x == "center" else x)
        KColor(rgba=color)
        Rectangle(texture=tex, size=tex.size, pos=(tx, y))

    def _redraw(self, *_):
        self.canvas.clear()
        data = list(self.data)
        if not data or self.width < dp(40) or self.height < dp(40):
            return

        left   = dp(38)
        right  = dp(8)
        top    = dp(10)
        bottom = dp(16)

        plot_x = self.x + left
        plot_y = self.y + bottom
        plot_w = self.width - left - right
        plot_h = self.height - top - bottom
        if plot_w <= 0 or plot_h <= 0:
            return

        max_val = max(data) or 1.0
        n = len(data)
        slot_w = plot_w / n
        bar_w = max(dp(2), slot_w * 0.7)
        bar_off = (slot_w - bar_w) / 2.0

        with self.canvas:
            # Baseline + top gridline
            KColor(rgba=self.axis_color)
            Rectangle(pos=(plot_x, plot_y), size=(plot_w, dp(1)))
            Rectangle(pos=(plot_x, plot_y + plot_h), size=(plot_w, dp(1)))

            # Bars
            KColor(rgba=self.bar_color)
            for i, val in enumerate(data):
                h = (max(0.0, val) / max_val) * plot_h
                bx = plot_x + i * slot_w + bar_off
                Rectangle(pos=(bx, plot_y), size=(bar_w, max(dp(1), h)))

            # Y-axis labels (max at top, 0 at baseline)
            self._text(self._fmt(max_val), plot_x - dp(4), plot_y + plot_h - sp(6),
                       sp(9), self.label_color, anchor_x="right")
            self._text("0", plot_x - dp(4), plot_y - sp(4),
                       sp(9), self.label_color, anchor_x="right")

            # X-axis labels: first, middle, last (avoids clutter at 30 days)
            labels = list(self.labels)
            if labels and len(labels) == n:
                idxs = sorted(set([0, n // 2, n - 1]))
                for i in idxs:
                    cx = plot_x + i * slot_w + slot_w / 2.0
                    self._text(labels[i], cx, self.y, sp(8),
                               self.label_color, anchor_x="center")

    @staticmethod
    def _fmt(v):
        if v >= 100:
            return f"{v:.0f}"
        if v >= 10:
            return f"{v:.1f}"
        return f"{v:.2f}"
