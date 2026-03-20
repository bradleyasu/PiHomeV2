"""Hex -- Two-player connection strategy game for PiHome."""

import collections
import json
import math
import os
import random

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Mesh, Rectangle, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import (
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from interface.pihomescreen import PiHomeScreen
from util.configuration import CONFIG
from util.helpers import toast
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/HexGame/hexgame.kv")

# ── Constants ────────────────────────────────────────────────────────────

EMPTY = 0
BLUE = 1   # Player 1 — connects left edge (col=0) to right edge (col=N-1)
RED = 2    # Player 2 — connects top edge (row=0) to bottom edge (row=N-1)

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state.json")

# Hex neighbor offsets (axial-style on rhombus grid)
HEX_DIRS = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0)]

SQRT3 = math.sqrt(3)

# Color palette
C_HEX_EMPTY = [0.16, 0.16, 0.21, 1]
C_HEX_BORDER = [0.28, 0.28, 0.34, 0.5]
C_BLUE = [0.22, 0.50, 0.95, 1]
C_BLUE_DIM = [0.18, 0.35, 0.70, 0.5]
C_RED = [0.92, 0.25, 0.15, 1]
C_RED_DIM = [0.60, 0.18, 0.12, 0.5]
C_LAST_MOVE = [1.0, 1.0, 1.0, 0.5]
C_WIN_GLOW = [1.0, 0.85, 0.20, 0.45]
C_GOLD = [1.0, 0.78, 0.20, 1]
C_TEXT = [0.80, 0.84, 0.92, 1]
C_TEXT_DIM = [0.42, 0.46, 0.55, 0.7]
C_ACCENT = [0.30, 0.55, 0.97, 1]
C_GREEN = [0.20, 0.75, 0.35, 1]
C_BTN = [0.12, 0.16, 0.26, 1]
C_BTN_ACTIVE = [0.18, 0.24, 0.38, 1]


# ── Game State ───────────────────────────────────────────────────────────


class HexState:
    """Pure game logic and persistence for Hex."""

    def __init__(self, size=11):
        self._size = size
        self.reset()

    def reset(self):
        sz = self._size
        self.phase = "welcome"
        self.turn = BLUE
        self.board = [[EMPTY] * sz for _ in range(sz)]
        self.winner = None
        self.names = {BLUE: "Player 1", RED: "Player 2"}
        self.moves = {BLUE: 0, RED: 0}
        self.last_move = None
        self.win_path = []

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, val):
        if val != self._size:
            self._size = val
            self.reset()

    def place(self, row, col):
        """Place current player's stone. Returns (ok, win_path_or_None)."""
        if self.board[row][col] != EMPTY:
            return False, None
        self.board[row][col] = self.turn
        self.moves[self.turn] += 1
        self.last_move = (row, col)

        path = self._check_win(self.turn)
        if path:
            self.winner = self.turn
            self.win_path = path
            self.phase = "game_over"
            return True, path

        self.turn = RED if self.turn == BLUE else BLUE
        return True, None

    def _neighbors(self, r, c):
        for dr, dc in HEX_DIRS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self._size and 0 <= nc < self._size:
                yield nr, nc

    def _check_win(self, player):
        """BFS from one edge; return winning path if connected, else None."""
        sz = self._size
        parent = {}
        queue = collections.deque()

        if player == BLUE:
            for r in range(sz):
                if self.board[r][0] == player:
                    queue.append((r, 0))
                    parent[(r, 0)] = None
            target = lambda r, c: c == sz - 1
        else:
            for c in range(sz):
                if self.board[0][c] == player:
                    queue.append((0, c))
                    parent[(0, c)] = None
            target = lambda r, c: r == sz - 1

        while queue:
            r, c = queue.popleft()
            if target(r, c):
                path = []
                cell = (r, c)
                while cell is not None:
                    path.append(cell)
                    cell = parent[cell]
                return path
            for nr, nc in self._neighbors(r, c):
                if (nr, nc) not in parent and self.board[nr][nc] == player:
                    parent[(nr, nc)] = (r, c)
                    queue.append((nr, nc))
        return None

    # ── Persistence ──

    def save(self):
        try:
            data = {
                "size": self._size,
                "phase": self.phase,
                "turn": self.turn,
                "board": self.board,
                "winner": self.winner,
                "names": {str(k): v for k, v in self.names.items()},
                "moves": {str(k): v for k, v in self.moves.items()},
                "last_move": self.last_move,
                "win_path": self.win_path,
            }
            with open(SAVE_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            PIHOME_LOGGER.error(f"Hex save: {e}")

    def load(self):
        try:
            if not os.path.exists(SAVE_FILE):
                return False
            with open(SAVE_FILE) as f:
                d = json.load(f)
            self._size = d.get("size", 11)
            self.phase = d["phase"]
            self.turn = d["turn"]
            self.board = d["board"]
            self.winner = d.get("winner")
            self.names = {int(k): v for k, v in d.get("names", {}).items()}
            self.moves = {int(k): v for k, v in d.get("moves", {}).items()}
            self.last_move = tuple(d["last_move"]) if d.get("last_move") else None
            self.win_path = [tuple(c) for c in d.get("win_path", [])]
            return True
        except Exception as e:
            PIHOME_LOGGER.error(f"Hex load: {e}")
            return False


# ── Particle Overlay ─────────────────────────────────────────────────────


class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "r", "g", "b", "a", "sz", "life", "age")


class ParticleOverlay(Widget):
    """Lightweight particle effects."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._particles = []
        self._event = None

    def burst(self, x, y, color, count=20, speed=120, life=0.8):
        for _ in range(count):
            ang = random.uniform(0, 2 * math.pi)
            v = random.uniform(speed * 0.3, speed)
            p = _Particle()
            p.x, p.y = x, y
            p.vx, p.vy = v * math.cos(ang), v * math.sin(ang)
            p.r, p.g, p.b = color[0], color[1], color[2]
            p.a = 1.0
            p.sz = random.uniform(dp(2), dp(5))
            p.life = life * random.uniform(0.5, 1.0)
            p.age = 0
            self._particles.append(p)
        if not self._event:
            self._event = Clock.schedule_interval(self._tick, 1 / 30)

    def clear_particles(self):
        self._particles.clear()
        if self._event:
            self._event.cancel()
            self._event = None
        self.canvas.clear()

    def _tick(self, dt):
        alive = []
        for p in self._particles:
            p.age += dt
            if p.age >= p.life:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy -= dp(180) * dt
            p.a = max(0.0, 1.0 - p.age / p.life)
            p.sz = max(dp(0.5), p.sz * (1 - dt * 0.6))
            alive.append(p)
        self._particles = alive
        self.canvas.clear()
        with self.canvas:
            for p in alive:
                Color(p.r, p.g, p.b, p.a)
                Ellipse(pos=(p.x - p.sz / 2, p.y - p.sz / 2), size=(p.sz, p.sz))
        if not alive and self._event:
            self._event.cancel()
            self._event = None


# ── Hex Board Widget ─────────────────────────────────────────────────────


class HexBoard(Widget):
    """Canvas-drawn hex grid with touch support."""

    interactive = BooleanProperty(True)
    cell_tap_callback = ObjectProperty(None, allownone=True)

    def __init__(self, game_state, **kwargs):
        self._gs = game_state
        self._radius = dp(20)
        self._ox = 0
        self._oy = 0
        self._tex_cache = {}
        super().__init__(**kwargs)
        self.bind(pos=self._mark_dirty, size=self._recalc)

    def _recalc(self, *args):
        if self.width < dp(50) or self.height < dp(50):
            return
        bs = self._gs.size
        # Board spans in radius-units:
        #   width  = (1.5*(bs-1) + 1) * sqrt(3) * r   (column + row offset)
        #   height = (1.5*(bs-1) + 2) * r
        # Actually derived from center positions + hex extent:
        w_units = SQRT3 * (1.5 * (bs - 1) + 1)
        h_units = 1.5 * (bs - 1) + 2

        r_w = (self.width - dp(16)) / w_units
        r_h = (self.height - dp(16)) / h_units
        self._radius = min(r_w, r_h)

        # Compute origin so board is centered
        board_w = w_units * self._radius
        board_h = h_units * self._radius
        self._ox = self.x + (self.width - board_w) / 2 + self._radius * SQRT3 / 2
        self._oy = self.y + (self.height - board_h) / 2 + self._radius
        self._mark_dirty()

    def _hex_center(self, row, col):
        r = self._radius
        w = r * SQRT3
        bs = self._gs.size
        x = self._ox + col * w + row * w / 2
        y = self._oy + (bs - 1 - row) * 1.5 * r
        return x, y

    def _hex_corners(self, cx, cy, r):
        corners = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            corners.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        return corners

    def _pos2cell(self, pos):
        """Find hex cell nearest to screen position."""
        r = self._radius
        best, best_d = None, float("inf")
        bs = self._gs.size
        for row in range(bs):
            for col in range(bs):
                cx, cy = self._hex_center(row, col)
                d = math.hypot(pos[0] - cx, pos[1] - cy)
                if d < r * 0.95 and d < best_d:
                    best = (row, col)
                    best_d = d
        return best

    def _tex(self, text, size, color):
        key = (text, size, tuple(color))
        if key not in self._tex_cache:
            cl = CoreLabel(text=text, font_size=size, font_name="Nunito", color=color)
            cl.refresh()
            self._tex_cache[key] = cl.texture
        return self._tex_cache[key]

    def _mark_dirty(self, *args):
        Clock.schedule_once(lambda dt: self._redraw(), -1)

    def refresh(self):
        self._mark_dirty()

    def _redraw(self):
        r = self._radius
        if r < dp(3):
            return
        bs = self._gs.size
        gap = r * 0.92  # slightly smaller for visual gap between hexes

        self.canvas.clear()
        with self.canvas:
            win_set = set(tuple(c) for c in self._gs.win_path)

            for row in range(bs):
                for col in range(bs):
                    cx, cy = self._hex_center(row, col)
                    cell = self._gs.board[row][col]

                    # ── Fill ──
                    if cell == BLUE:
                        fill = C_BLUE
                    elif cell == RED:
                        fill = C_RED
                    else:
                        fill = C_HEX_EMPTY

                    self._draw_hex_fill(cx, cy, gap, fill)

                    # ── Win glow ──
                    if (row, col) in win_set:
                        self._draw_hex_fill(cx, cy, gap * 1.05, C_WIN_GLOW)

                    # ── Border ──
                    if col == 0 or col == bs - 1:
                        bc, bw = C_BLUE_DIM, dp(1.8)
                    elif row == 0 or row == bs - 1:
                        bc, bw = C_RED_DIM, dp(1.8)
                    else:
                        bc, bw = C_HEX_BORDER, dp(0.8)
                    self._draw_hex_outline(cx, cy, gap, bc, bw)

                    # ── Last move ring ──
                    if self._gs.last_move == (row, col):
                        self._draw_hex_outline(cx, cy, gap * 0.65, C_LAST_MOVE, dp(2))

            # ── Edge labels ──
            self._draw_edge_labels(bs, r)

    def _draw_hex_fill(self, cx, cy, r, color):
        corners = self._hex_corners(cx, cy, r)
        verts = [cx, cy, 0, 0]
        for vx, vy in corners:
            verts.extend([vx, vy, 0, 0])
        verts.extend([corners[0][0], corners[0][1], 0, 0])
        indices = list(range(8))
        Color(*color)
        Mesh(vertices=verts, indices=indices, mode="triangle_fan")

    def _draw_hex_outline(self, cx, cy, r, color, width=dp(0.8)):
        corners = self._hex_corners(cx, cy, r)
        points = []
        for vx, vy in corners:
            points.extend([vx, vy])
        points.extend(points[:2])
        Color(*color)
        Line(points=points, width=width)

    def _draw_edge_labels(self, bs, r):
        """Draw B/R labels near the board edges to indicate player direction."""
        Color(1, 1, 1, 1)

        # Blue labels near left and right edges
        mid_row = bs // 2
        # Left
        cx, cy = self._hex_center(mid_row, 0)
        t = self._tex("B", sp(10), C_BLUE)
        Rectangle(
            texture=t,
            pos=(cx - r * 1.6 - t.width / 2, cy - t.height / 2),
            size=t.size,
        )
        # Right
        cx, cy = self._hex_center(mid_row, bs - 1)
        t = self._tex("B", sp(10), C_BLUE)
        Rectangle(
            texture=t,
            pos=(cx + r * 1.6 - t.width / 2, cy - t.height / 2),
            size=t.size,
        )

        # Red labels near top and bottom edges
        mid_col = bs // 2
        # Top
        cx, cy = self._hex_center(0, mid_col)
        t = self._tex("R", sp(10), C_RED)
        Rectangle(
            texture=t,
            pos=(cx - t.width / 2, cy + r * 1.3),
            size=t.size,
        )
        # Bottom
        cx, cy = self._hex_center(bs - 1, mid_col)
        t = self._tex("R", sp(10), C_RED)
        Rectangle(
            texture=t,
            pos=(cx - t.width / 2, cy - r * 1.3 - t.height),
            size=t.size,
        )

    def on_touch_down(self, touch):
        if not self.interactive or self.disabled:
            return False
        if not self.collide_point(*touch.pos):
            return False
        cell = self._pos2cell(touch.pos)
        if cell and self.cell_tap_callback:
            self.cell_tap_callback(cell[0], cell[1])
            return True
        return False


# ── Main Screen ──────────────────────────────────────────────────────────


class HexGameScreen(PiHomeScreen):
    """Two-player Hex connection strategy game."""

    bg_color = ColorProperty([0.10, 0.10, 0.12, 1])
    header_color = ColorProperty([0.14, 0.14, 0.16, 1])
    text_color = ColorProperty([1, 1, 1, 1])
    muted_color = ColorProperty([1, 1, 1, 0.45])
    accent_color = ColorProperty([0.25, 0.52, 1.0, 1])
    status_color = ColorProperty([0.45, 0.45, 0.45, 1])

    status_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._game = HexState()
        self._particles = ParticleOverlay(size_hint=(1, 1))
        self._events = []
        self._board_widget = None
        self._board_size = 11
        self._load_config()

    # ── Config ───────────────────────────────────────────────────────────

    def _load_config(self):
        n1 = CONFIG.get("hexgame", "p1_name", "Player 1").strip()
        n2 = CONFIG.get("hexgame", "p2_name", "Player 2").strip()
        self._game.names[BLUE] = n1 or "Player 1"
        self._game.names[RED] = n2 or "Player 2"
        bs = CONFIG.get("hexgame", "board_size", "11").strip()
        self._board_size = int(bs) if bs in ("7", "9", "11") else 11

    def on_config_update(self, config):
        self._load_config()
        super().on_config_update(config)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def on_enter(self, *args):
        self._load_config()
        if self._game.load() and self._game.phase != "welcome":
            n1 = CONFIG.get("hexgame", "p1_name", "").strip()
            n2 = CONFIG.get("hexgame", "p2_name", "").strip()
            if n1:
                self._game.names[BLUE] = n1
            if n2:
                self._game.names[RED] = n2
        self._set_phase(self._game.phase)
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        self._cancel_events()
        self._particles.clear_particles()
        self._game.save()
        return super().on_pre_leave(*args)

    # ── Scheduling ───────────────────────────────────────────────────────

    def _cancel_events(self):
        for ev in self._events:
            ev.cancel()
        self._events.clear()

    def _sched(self, cb, delay):
        ev = Clock.schedule_once(cb, delay)
        self._events.append(ev)
        return ev

    # ── Phase management ─────────────────────────────────────────────────

    def _set_phase(self, phase):
        self._cancel_events()
        self._particles.clear_particles()
        self._game.phase = phase

        body = self.ids.get("body")
        if not body:
            return
        body.clear_widgets()

        builders = {
            "welcome": self._build_welcome,
            "play": self._build_play,
            "game_over": self._build_gameover,
        }
        view = builders.get(phase, self._build_welcome)()
        body.add_widget(view)
        body.add_widget(self._particles)

        if phase == "play":
            name = self._game.names[self._game.turn]
            color = "Blue" if self._game.turn == BLUE else "Red"
            self.status_text = f"{name}'s turn ({color})"
        elif phase == "game_over":
            self.status_text = "Game Over"
        else:
            self.status_text = ""

        self._game.save()

    # ── Welcome ──────────────────────────────────────────────────────────

    def _build_welcome(self):
        layout = FloatLayout()

        title = Label(
            text="HEX",
            font_name="Nunito",
            font_size=sp(50),
            bold=True,
            color=C_TEXT,
            size_hint=(1, None),
            height=dp(70),
            pos_hint={"center_x": 0.5, "center_y": 0.72},
        )
        layout.add_widget(title)
        title.opacity = 0
        title.font_size = sp(20)
        Animation(opacity=1, font_size=sp(50), d=0.6, t="out_back").start(title)

        sub = Label(
            text="Connect your edges to win",
            font_name="Nunito",
            font_size=sp(14),
            color=C_TEXT_DIM,
            size_hint=(1, None),
            height=dp(30),
            pos_hint={"center_x": 0.5, "center_y": 0.58},
        )
        layout.add_widget(sub)

        # Player indicators
        p1 = Label(
            text=f"{self._game.names[BLUE]} (Blue - left/right)",
            font_name="Nunito",
            font_size=sp(12),
            color=C_BLUE,
            size_hint=(1, None),
            height=dp(22),
            pos_hint={"center_x": 0.5, "center_y": 0.49},
        )
        layout.add_widget(p1)
        p2 = Label(
            text=f"{self._game.names[RED]} (Red - top/bottom)",
            font_name="Nunito",
            font_size=sp(12),
            color=C_RED,
            size_hint=(1, None),
            height=dp(22),
            pos_hint={"center_x": 0.5, "center_y": 0.43},
        )
        layout.add_widget(p2)

        new_btn = self._make_button("NEW GAME", self._on_new_game)
        new_btn.pos_hint = {"center_x": 0.5, "center_y": 0.28}
        layout.add_widget(new_btn)

        # Continue button
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE) as f:
                    d = json.load(f)
                if d.get("phase") not in ("welcome", "game_over", None):
                    cont = self._make_button("CONTINUE", self._on_continue, bg=C_GREEN)
                    cont.pos_hint = {"center_x": 0.5, "center_y": 0.15}
                    layout.add_widget(cont)
        except Exception:
            pass

        return layout

    # ── Play ─────────────────────────────────────────────────────────────

    def _build_play(self):
        layout = BoxLayout(orientation="horizontal", spacing=dp(4), padding=[dp(4)])

        # Hex board (takes most space)
        self._board_widget = HexBoard(
            self._game,
            interactive=True,
            cell_tap_callback=self._on_cell_tap,
            size_hint=(1, 1),
        )
        layout.add_widget(self._board_widget)

        # Side panel
        panel = BoxLayout(
            orientation="vertical",
            size_hint_x=None,
            width=dp(155),
            spacing=dp(8),
            padding=[dp(8), dp(12)],
        )

        # Turn indicator
        turn_title = Label(
            text="TURN",
            font_name="Nunito",
            font_size=sp(10),
            color=C_TEXT_DIM,
            size_hint_y=None,
            height=dp(18),
            halign="center",
            valign="middle",
        )
        turn_title.bind(size=turn_title.setter("text_size"))
        panel.add_widget(turn_title)

        # Current player
        turn_color = C_BLUE if self._game.turn == BLUE else C_RED
        turn_name = self._game.names[self._game.turn]
        turn_label = Label(
            text=turn_name,
            font_name="Nunito",
            font_size=sp(16),
            bold=True,
            color=turn_color,
            size_hint_y=None,
            height=dp(28),
            halign="center",
            valign="middle",
        )
        turn_label.bind(size=turn_label.setter("text_size"))
        panel.add_widget(turn_label)

        # Color indicator dot
        dot = Widget(size_hint=(None, None), size=(dp(14), dp(14)), pos_hint={"center_x": 0.5})
        with dot.canvas:
            Color(*turn_color)
            dot._ell = Ellipse(pos=dot.pos, size=dot.size)
        dot.bind(pos=lambda w, p: setattr(w._ell, "pos", p))
        panel.add_widget(dot)

        # Divider
        panel.add_widget(Widget(size_hint_y=None, height=dp(12)))

        # Stats
        for player, color, label_text in [
            (BLUE, C_BLUE, "Blue"),
            (RED, C_RED, "Red"),
        ]:
            row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(6))
            # Color dot
            pdot = Widget(size_hint=(None, None), size=(dp(10), dp(10)))
            with pdot.canvas:
                Color(*color)
                pdot._e = Ellipse(pos=pdot.pos, size=pdot.size)
            pdot.bind(pos=lambda w, p: setattr(w._e, "pos", p))
            row.add_widget(pdot)
            # Name + count
            sl = Label(
                text=f"{self._game.names[player]}: {self._game.moves[player]}",
                font_name="Nunito",
                font_size=sp(10),
                color=color,
                halign="left",
                valign="middle",
            )
            sl.bind(size=sl.setter("text_size"))
            row.add_widget(sl)
            panel.add_widget(row)

        panel.add_widget(Widget())  # Spacer

        # Board size info
        bs_label = Label(
            text=f"{self._game.size}x{self._game.size} board",
            font_name="Nunito",
            font_size=sp(9),
            color=C_TEXT_DIM,
            size_hint_y=None,
            height=dp(18),
            halign="center",
            valign="middle",
        )
        bs_label.bind(size=bs_label.setter("text_size"))
        panel.add_widget(bs_label)

        # New Game button
        ng = self._make_button(
            "NEW GAME", self._on_new_game, width=dp(140), height=dp(36)
        )
        ng.size_hint = (1, None)
        ng.height = dp(36)
        panel.add_widget(ng)

        layout.add_widget(panel)
        return layout

    # ── Game Over ────────────────────────────────────────────────────────

    def _build_gameover(self):
        layout = FloatLayout()

        # Show the board in the background (non-interactive, with win path)
        board = HexBoard(self._game, interactive=False, size_hint=(0.7, 0.85))
        board.pos_hint = {"x": 0.0, "center_y": 0.5}
        layout.add_widget(board)

        # Overlay panel on the right
        winner = self._game.winner or BLUE
        wcolor = C_BLUE if winner == BLUE else C_RED
        wname = self._game.names[winner]

        # Winner text
        win_lbl = Label(
            text=f"{wname}\nWINS!",
            font_name="Nunito",
            font_size=sp(10),
            bold=True,
            color=C_GOLD,
            size_hint=(None, None),
            size=(dp(200), dp(80)),
            pos_hint={"right": 0.98, "center_y": 0.72},
            halign="center",
            valign="middle",
        )
        win_lbl.bind(size=win_lbl.setter("text_size"))
        layout.add_widget(win_lbl)
        Animation(font_size=sp(28), d=0.7, t="out_back").start(win_lbl)

        # Stats
        for p in (BLUE, RED):
            pc = C_BLUE if p == BLUE else C_RED
            is_w = p == winner
            stat = Label(
                text=f"{self._game.names[p]}: {self._game.moves.get(p, 0)} moves",
                font_name="Nunito",
                font_size=sp(12),
                color=C_GOLD if is_w else C_TEXT,
                size_hint=(None, None),
                size=(dp(200), dp(22)),
                pos_hint={
                    "right": 0.98,
                    "center_y": 0.52 if p == BLUE else 0.44,
                },
                halign="center",
                valign="middle",
            )
            stat.bind(size=stat.setter("text_size"))
            layout.add_widget(stat)

        # New Game
        btn = self._make_button("NEW GAME", self._on_new_game)
        btn.pos_hint = {"right": 0.98, "center_y": 0.22}
        layout.add_widget(btn)

        # Victory particles
        self._sched(lambda dt: self._victory_burst(), 0.3)

        return layout

    def _victory_burst(self):
        if not self.is_open or self._game.phase != "game_over":
            return
        body = self.ids.get("body")
        if not body:
            return
        wcolor = C_BLUE if self._game.winner == BLUE else C_RED
        for _ in range(3):
            x = random.uniform(body.x + dp(60), body.x + body.width - dp(60))
            y = random.uniform(body.y + dp(80), body.y + body.height - dp(60))
            color = random.choice([wcolor, C_GOLD, C_ACCENT, [0.9, 0.3, 0.9, 1]])
            self._particles.burst(x, y, color, count=16, speed=dp(90), life=1.0)
        self._sched(lambda dt: self._victory_burst(), 0.7)

    def _rebuild_play(self):
        """Rebuild the play view to refresh the side panel (turn/stats)."""
        body = self.ids.get("body")
        if not body:
            return
        body.clear_widgets()
        view = self._build_play()
        body.add_widget(view)
        body.add_widget(self._particles)
        name = self._game.names[self._game.turn]
        color = "Blue" if self._game.turn == BLUE else "Red"
        self.status_text = f"{name}'s turn ({color})"

    # ── Button helper ────────────────────────────────────────────────────

    def _make_button(self, text, callback, bg=None, width=dp(200), height=dp(44)):
        bg = list(bg or C_BTN)
        btn = BoxLayout(
            size_hint=(None, None), size=(width, height), padding=[dp(16), dp(8)]
        )
        with btn.canvas.before:
            btn._bg_ci = Color(*bg)
            btn._bg_rr = RoundedRectangle(
                pos=btn.pos, size=btn.size, radius=[dp(8)]
            )
        btn.bind(
            pos=lambda w, p: setattr(w._bg_rr, "pos", p),
            size=lambda w, s: setattr(w._bg_rr, "size", s),
        )
        lbl = Label(
            text=text,
            font_name="Nunito",
            font_size=sp(14),
            bold=True,
            color=C_TEXT,
            halign="center",
            valign="middle",
        )
        lbl.bind(size=lbl.setter("text_size"))
        btn.add_widget(lbl)

        orig = list(bg)

        def _td(w, touch):
            if w.collide_point(*touch.pos) and not w.disabled:
                w._bg_ci.rgba = C_BTN_ACTIVE
                touch.grab(w)
                return True
            return False

        def _tu(w, touch):
            if touch.grab_current == w:
                touch.ungrab(w)
                w._bg_ci.rgba = orig
                if w.collide_point(*touch.pos) and callback:
                    callback()
                return True
            return False

        btn.bind(on_touch_down=_td, on_touch_up=_tu)
        return btn

    # ── Game Actions ─────────────────────────────────────────────────────

    def _on_new_game(self):
        self._load_config()
        self._game.size = self._board_size
        self._game.reset()
        self._game.names[BLUE] = CONFIG.get("hexgame", "p1_name", "Player 1").strip() or "Player 1"
        self._game.names[RED] = CONFIG.get("hexgame", "p2_name", "Player 2").strip() or "Player 2"
        try:
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)
        except Exception:
            pass
        self._set_phase("play")

    def _on_continue(self):
        self._game.load()
        self._load_config()
        self._set_phase(self._game.phase)

    def _on_cell_tap(self, row, col):
        if self._game.phase != "play":
            return
        if self._game.board[row][col] != EMPTY:
            toast("Cell already taken!", "info", 1)
            return

        ok, win_path = self._game.place(row, col)
        if not ok:
            return

        # Capture board center before rebuild (for effects)
        bw = self._board_widget
        if bw:
            cx, cy = bw._hex_center(row, col)
            bcx, bcy = bw.center_x, bw.center_y
        else:
            cx, cy = dp(400), dp(240)
            bcx, bcy = cx, cy

        # Use a bright highlight color for particles so they're visible on the stone
        if self._game.board[row][col] == BLUE:
            spark_color = [0.55, 0.78, 1.0, 1]  # light blue
        else:
            spark_color = [1.0, 0.6, 0.4, 1]    # light coral

        if win_path:
            # Winner — update board visuals to show win path, then transition
            if bw:
                bw.refresh()
            self._particles.burst(cx, cy, spark_color, count=14, speed=dp(55), life=0.6)
            name = self._game.names[self._game.winner]
            self._show_float(f"{name} wins!", bcx, bcy, C_GOLD, sp(22))
            self._game.save()
            self._sched(lambda dt: self._set_phase("game_over"), 2.0)
        else:
            # Rebuild the play view so the side panel updates
            self._game.save()
            self._rebuild_play()
            # Burst particles after rebuild so they render on top
            # Use saved coordinates from the old board widget
            self._sched(
                lambda dt, x=cx, y=cy, c=spark_color: self._particles.burst(
                    x, y, c, count=14, speed=dp(55), life=0.6
                ),
                0.05,
            )

    def _show_float(self, text, x, y, color, size=sp(18)):
        body = self.ids.get("body")
        if not body:
            return
        lbl = Label(
            text=text,
            font_name="Nunito",
            font_size=size,
            bold=True,
            color=color,
            pos=(x - dp(70), y),
            size_hint=(None, None),
            size=(dp(140), dp(30)),
            halign="center",
            valign="middle",
        )
        lbl.text_size = lbl.size
        body.add_widget(lbl)
        anim = Animation(y=y + dp(60), opacity=0, d=1.5, t="out_quad")
        anim.bind(
            on_complete=lambda *a: body.remove_widget(lbl) if lbl.parent else None
        )
        anim.start(lbl)

    # ── Rotary Encoder ───────────────────────────────────────────────────

    def on_rotary_pressed(self):
        return True

    def on_rotary_turn(self, direction, button_pressed):
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True
