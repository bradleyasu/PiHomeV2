"""Interactive Nanoleaf panel layout renderer for PiHome.

Draws Nanoleaf panels (triangles, mini-triangles, hexagons, squares) on a
Kivy canvas matching their physical wall layout.  Panels are tappable —
touching one dispatches an ``on_panel_selected`` event with the panel ID.

Supported shape types (Nanoleaf OpenAPI)
----------------------------------------
  0  Triangle (original Light Panels)
  2  Square (Canvas)
  4  Hexagon (Elements)
  7  Hexagon (Shapes)
  8  Triangle (Shapes)
  9  Mini Triangle (Shapes)

Controller shapes (1, 3, 12) are skipped.
"""

import math

from kivy.graphics import Color, Line, Mesh
from kivy.properties import (
    ColorProperty, DictProperty, ListProperty, NumericProperty,
)
from kivy.uix.widget import Widget

from util.phlog import PIHOME_LOGGER


# ── Shape type constants ──────────────────────────────────────────────────────

_SHAPE_OLD_TRIANGLE    = 0
_SHAPE_RHYTHM          = 1
_SHAPE_SQUARE          = 2
_SHAPE_CTRL_SQUARE     = 3
_SHAPE_ELEM_HEXAGON    = 4
_SHAPE_SHAPES_HEXAGON  = 7
_SHAPE_SHAPES_TRIANGLE = 8
_SHAPE_SHAPES_MINI_TRI = 9
_SHAPE_CONTROLLER      = 12

_SKIP_SHAPES = {_SHAPE_RHYTHM, _SHAPE_CTRL_SQUARE, _SHAPE_CONTROLLER}

# Per-shape-type side lengths in Nanoleaf coordinate units.
# The global ``sideLength`` field is deprecated (fw 5+); these are the
# canonical values taken from the Nanoleaf OpenAPI specification.
_SHAPE_SIDE = {
    _SHAPE_OLD_TRIANGLE:    150,   # Original Light Panels
    _SHAPE_SQUARE:          100,   # Canvas
    _SHAPE_ELEM_HEXAGON:    134,   # Elements Hexagon
    _SHAPE_SHAPES_HEXAGON:   67,   # Shapes Hexagon
    _SHAPE_SHAPES_TRIANGLE: 134,   # Shapes Triangle
    _SHAPE_SHAPES_MINI_TRI:  67,   # Shapes Mini Triangle
}

_TRIANGLE_SHAPES = {_SHAPE_OLD_TRIANGLE, _SHAPE_SHAPES_TRIANGLE, _SHAPE_SHAPES_MINI_TRI}
_HEXAGON_SHAPES  = {_SHAPE_ELEM_HEXAGON, _SHAPE_SHAPES_HEXAGON}
_SQUARE_SHAPES   = {_SHAPE_SQUARE}


class PanelCanvas(Widget):
    """Renders Nanoleaf panels scaled and centred inside the widget."""

    panels = ListProperty([])                     # list of panel dicts from layout API
    panel_colors = DictProperty({})               # {panel_id: (r, g, b)} 0-255
    selected_panel = NumericProperty(-1)           # -1 = none
    side_length = NumericProperty(150)             # from layout API
    highlight_color = ColorProperty([1, 1, 1, 0.9])
    dim_color = ColorProperty([0.22, 0.22, 0.25, 1])  # default unlit panel

    __events__ = ("on_panel_selected",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._panel_verts = {}   # {panel_id: [(x,y), ...]}
        self.bind(
            panels=self._redraw, panel_colors=self._redraw,
            selected_panel=self._redraw, size=self._redraw, pos=self._redraw,
            side_length=self._redraw,
        )

    # ── Geometry helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _tri_vertices(cx, cy, side, orientation):
        """Return 3 vertices of an equilateral triangle centred at (cx, cy).

        Nanoleaf orientation: 0° = flat edge at bottom, vertex pointing up.
        Rotations are in 60° increments clockwise.
        """
        r = side / math.sqrt(3)  # circumradius
        verts = []
        for i in range(3):
            # 90° base puts first vertex at top; orientation rotates clockwise
            # so we subtract to match Nanoleaf's clockwise convention
            a = math.radians(90 - orientation + i * 120)
            verts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return verts

    @staticmethod
    def _hex_vertices(cx, cy, side, orientation):
        """Return 6 vertices of a regular hexagon centred at (cx, cy).

        Nanoleaf hexagons are flat-top by default (flat edge on top/bottom).
        ``side`` is the circumradius (center to vertex = side length).
        """
        verts = []
        for i in range(6):
            # 0° = flat-top: first vertex at right, flat edges top/bottom
            a = math.radians(i * 60 - orientation)
            verts.append((cx + side * math.cos(a), cy + side * math.sin(a)))
        return verts

    @staticmethod
    def _square_vertices(cx, cy, side, orientation):
        """Return 4 vertices of a square centred at (cx, cy)."""
        half = side / 2.0
        verts = []
        for i in range(4):
            a = math.radians(45 + i * 90 - orientation)
            d = half * math.sqrt(2)
            verts.append((cx + d * math.cos(a), cy + d * math.sin(a)))
        return verts

    def _compute_transform(self):
        """Return (scale, offset_x, offset_y) to map layout coords into widget.

        The Nanoleaf coordinate system has Y increasing upward — same as Kivy,
        so no Y-flip is needed.
        """
        renderable = [p for p in self.panels if p.get("shapeType") not in _SKIP_SHAPES]
        if not renderable:
            return 1.0, self.x, self.y

        xs = [p["x"] for p in renderable]
        ys = [p["y"] for p in renderable]

        # Use the largest per-shape side length as margin; fall back to
        # self.side_length if it's nonzero, otherwise use 134 (triangle).
        margin = max(
            (_SHAPE_SIDE.get(p.get("shapeType", 8), 134) for p in renderable),
            default=self.side_length or 134,
        )
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        layout_w = (max_x - min_x) + margin * 2 or margin * 2
        layout_h = (max_y - min_y) + margin * 2 or margin * 2

        pad = 16
        avail_w = max(1, self.width - pad * 2)
        avail_h = max(1, self.height - pad * 2)
        scale = min(avail_w / layout_w, avail_h / layout_h)

        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        off_x = self.x + self.width / 2.0 - center_x * scale
        off_y = self.y + self.height / 2.0 - center_y * scale
        return scale, off_x, off_y

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _get_panel_vertices(self, shape, px, py, scale, orientation):
        """Compute vertices for a given shape type.

        Uses per-shape-type side lengths from ``_SHAPE_SIDE`` instead of the
        deprecated global ``sideLength`` field (which can be 0 or wrong in
        mixed layouts since firmware 5.0).
        """
        # Look up the canonical side for this shape; fall back to sideLength
        shape_side = _SHAPE_SIDE.get(shape, self.side_length) * scale

        if shape in _TRIANGLE_SHAPES:
            return self._tri_vertices(px, py, shape_side, orientation)

        if shape in _HEXAGON_SHAPES:
            # For regular hexagons circumradius == side length, so pass
            # shape_side directly (67 units for Shapes Hexagons).
            return self._hex_vertices(px, py, shape_side, orientation)

        if shape in _SQUARE_SHAPES:
            return self._square_vertices(px, py, shape_side, orientation)

        # Unknown shape — render as small hexagon so it's still visible
        return self._hex_vertices(px, py, shape_side * 0.5, orientation)

    def _redraw(self, *args):
        self.canvas.after.clear()
        self._panel_verts.clear()

        if not self.panels:
            return

        scale, off_x, off_y = self._compute_transform()
        PIHOME_LOGGER.info(
            f"Nanoleaf: _redraw {len(self.panels)} panels, "
            f"selected={self.selected_panel}, scale={scale:.3f}, "
            f"colors={len(self.panel_colors)}"
        )

        with self.canvas.after:
            for panel in self.panels:
                shape = panel.get("shapeType", _SHAPE_SHAPES_TRIANGLE)
                if shape in _SKIP_SHAPES:
                    continue

                pid = panel.get("panelId", 0)
                px = panel["x"] * scale + off_x
                py = panel["y"] * scale + off_y
                o = panel.get("o", 0)

                verts = self._get_panel_vertices(shape, px, py, scale, o)
                self._panel_verts[pid] = verts

                # Fill colour
                rgb = self.panel_colors.get(pid)
                if rgb:
                    Color(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1)
                else:
                    Color(*self.dim_color)

                # Filled polygon via Mesh (triangle_fan works for convex shapes)
                mesh_v = []
                for vx, vy in verts:
                    mesh_v.extend([vx, vy, 0, 0])
                n = len(verts)
                if n == 3:
                    indices = [0, 1, 2]
                else:
                    # triangle_fan: vertex 0 is the hub
                    indices = []
                    for i in range(1, n - 1):
                        indices.extend([0, i, i + 1])
                Mesh(vertices=mesh_v, indices=indices, mode="triangle_fan")

                # Outline
                pts = []
                for vx, vy in verts:
                    pts.extend([vx, vy])
                pts.extend([verts[0][0], verts[0][1]])  # close

                if pid == self.selected_panel:
                    # Bright cyan outline so selection is visible on any panel color
                    Color(0, 1, 1, 1)
                    Line(points=pts, width=3)
                    # Inner white glow for extra contrast
                    Color(1, 1, 1, 0.5)
                    Line(points=pts, width=1.5)
                else:
                    Color(1, 1, 1, 0.15)
                    Line(points=pts, width=1.2)

    # ── Hit testing ───────────────────────────────────────────────────────────

    @staticmethod
    def _point_in_polygon(px, py, verts):
        """Ray-casting point-in-polygon test (works for any convex/concave shape)."""
        n = len(verts)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = verts[i]
            xj, yj = verts[j]
            if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        PIHOME_LOGGER.info(
            f"Nanoleaf: PanelCanvas touch at ({touch.x:.0f}, {touch.y:.0f}), "
            f"widget pos={self.pos}, size={self.size}, "
            f"panels={len(self._panel_verts)}"
        )
        for pid, verts in self._panel_verts.items():
            if self._point_in_polygon(touch.x, touch.y, verts):
                PIHOME_LOGGER.info(f"Nanoleaf: hit panel {pid}")
                self.selected_panel = pid
                self.dispatch("on_panel_selected", pid)
                return True
        PIHOME_LOGGER.info("Nanoleaf: touch missed all panels")
        return False

    def on_panel_selected(self, panel_id):
        """Default handler — overridden or bound by the parent screen."""
        pass
