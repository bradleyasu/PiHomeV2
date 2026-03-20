"""Battleship — Two-player async naval combat for PiHome."""

import json
import math
import os
import random

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
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

Builder.load_file("./screens/Battleship/battleship.kv")

# ── Constants ────────────────────────────────────────────────────────────

GRID_SIZE = 10
SHIPS = [
    {"name": "Carrier", "size": 5},
    {"name": "Battleship", "size": 4},
    {"name": "Cruiser", "size": 3},
    {"name": "Submarine", "size": 3},
    {"name": "Destroyer", "size": 2},
]
TOTAL_HP = sum(s["size"] for s in SHIPS)  # 17

WATER = 0
MISS = 1
HIT = 2

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state.json")

# Game palette (nautical theme — independent of app theme)
C_OCEAN = [0.06, 0.10, 0.22, 1]
C_WATER = [0.08, 0.14, 0.28, 1]
C_GRID_LINE = [0.14, 0.22, 0.40, 0.4]
C_SHIP = [0.32, 0.40, 0.52, 1]
C_SHIP_SUNK = [0.40, 0.10, 0.08, 1]
C_HIT = [0.90, 0.22, 0.10, 1]
C_HIT_GLOW = [1.0, 0.35, 0.12, 0.18]
C_MISS = [0.30, 0.40, 0.60, 0.5]
C_TEXT = [0.75, 0.84, 0.96, 1]
C_TEXT_DIM = [0.40, 0.50, 0.68, 0.7]
C_ACCENT = [0.30, 0.55, 0.97, 1]
C_GREEN = [0.20, 0.75, 0.35, 1]
C_RED = [0.90, 0.20, 0.10, 1]
C_GOLD = [1.0, 0.78, 0.20, 1]
C_BTN = [0.12, 0.20, 0.38, 1]
C_BTN_ACTIVE = [0.18, 0.30, 0.52, 1]
C_SELECTED = [0.25, 0.50, 0.90, 0.35]


# ── Game State ───────────────────────────────────────────────────────────


class GameState:
    """Pure game logic and persistence."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.phase = "welcome"
        self.turn = 1
        self.boards = {p: [[0] * GRID_SIZE for _ in range(GRID_SIZE)] for p in (1, 2)}
        self.attacks = {p: [[0] * GRID_SIZE for _ in range(GRID_SIZE)] for p in (1, 2)}
        self.ships = {1: [], 2: []}
        self.sunk = {1: set(), 2: set()}
        self.winner = None
        self.names = {1: "Player 1", 2: "Player 2"}
        self.shots = {1: 0, 2: 0}
        self.hits = {1: 0, 2: 0}

    def can_place(self, player, ship_idx, row, col, horizontal):
        size = SHIPS[ship_idx]["size"]
        for i in range(size):
            r = row if horizontal else row + i
            c = col + i if horizontal else col
            if not (0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE):
                return False
            if self.boards[player][r][c] != 0:
                return False
        return True

    def place_ship(self, player, ship_idx, row, col, horizontal):
        if not self.can_place(player, ship_idx, row, col, horizontal):
            return False
        size = SHIPS[ship_idx]["size"]
        cells = []
        for i in range(size):
            r = row if horizontal else row + i
            c = col + i if horizontal else col
            self.boards[player][r][c] = ship_idx + 1
            cells.append([r, c])
        self.ships[player].append(
            {"idx": ship_idx, "cells": cells, "row": row, "col": col, "h": horizontal}
        )
        return True

    def remove_ship(self, player, ship_idx):
        for i, s in enumerate(self.ships[player]):
            if s["idx"] == ship_idx:
                for r, c in s["cells"]:
                    self.boards[player][r][c] = 0
                self.ships[player].pop(i)
                return True
        return False

    def placed_indices(self, player):
        return {s["idx"] for s in self.ships[player]}

    def all_placed(self, player):
        return len(self.ships[player]) == len(SHIPS)

    def fire(self, attacker, row, col):
        """Returns (is_hit, sunk_name, game_over) or None if cell already attacked."""
        defender = 3 - attacker
        if self.attacks[attacker][row][col] != 0:
            return None
        self.shots[attacker] += 1
        cell = self.boards[defender][row][col]
        if cell != 0:
            self.attacks[attacker][row][col] = HIT
            self.hits[attacker] += 1
            sunk = self._check_sunk(attacker, defender, cell)
            over = self.hits[attacker] >= TOTAL_HP
            if over:
                self.winner = attacker
                self.phase = "game_over"
            return True, sunk, over
        else:
            self.attacks[attacker][row][col] = MISS
            return False, None, False

    def _check_sunk(self, attacker, defender, ship_id):
        for s in self.ships[defender]:
            if s["idx"] + 1 == ship_id:
                if all(self.attacks[attacker][r][c] == HIT for r, c in s["cells"]):
                    self.sunk[attacker].add(s["idx"])
                    return SHIPS[s["idx"]]["name"]
        return None

    def sunk_cells_for(self, viewer):
        """Cells of enemy ships sunk by viewer."""
        defender = 3 - viewer
        cells = set()
        for s in self.ships[defender]:
            if s["idx"] in self.sunk[viewer]:
                cells.update(tuple(c) for c in s["cells"])
        return cells

    def my_sunk_cells(self, player):
        """Cells of player's own ships that enemy has fully sunk."""
        attacker = 3 - player
        cells = set()
        for s in self.ships[player]:
            if all(self.attacks[attacker][r][c] == HIT for r, c in s["cells"]):
                cells.update(tuple(c) for c in s["cells"])
        return cells

    # ── Persistence ──

    def save(self):
        try:
            data = {
                "phase": self.phase,
                "turn": self.turn,
                "boards": self.boards,
                "attacks": self.attacks,
                "ships": {str(k): v for k, v in self.ships.items()},
                "sunk": {str(k): list(v) for k, v in self.sunk.items()},
                "winner": self.winner,
                "names": {str(k): v for k, v in self.names.items()},
                "shots": {str(k): v for k, v in self.shots.items()},
                "hits": {str(k): v for k, v in self.hits.items()},
            }
            with open(SAVE_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            PIHOME_LOGGER.error(f"Battleship save: {e}")

    def load(self):
        try:
            if not os.path.exists(SAVE_FILE):
                return False
            with open(SAVE_FILE) as f:
                d = json.load(f)
            self.phase = d["phase"]
            self.turn = d["turn"]
            self.boards = {int(k): v for k, v in d["boards"].items()}
            self.attacks = {int(k): v for k, v in d["attacks"].items()}
            self.ships = {int(k): v for k, v in d["ships"].items()}
            self.sunk = {int(k): set(v) for k, v in d["sunk"].items()}
            self.winner = d.get("winner")
            self.names = {int(k): v for k, v in d.get("names", {}).items()}
            self.shots = {int(k): v for k, v in d.get("shots", {}).items()}
            self.hits = {int(k): v for k, v in d.get("hits", {}).items()}
            return True
        except Exception as e:
            PIHOME_LOGGER.error(f"Battleship load: {e}")
            return False


# ── Particle Overlay ─────────────────────────────────────────────────────


class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "r", "g", "b", "a", "sz", "life", "age")


class ParticleOverlay(Widget):
    """Lightweight particle effects rendered via canvas."""

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
                Ellipse(
                    pos=(p.x - p.sz / 2, p.y - p.sz / 2), size=(p.sz, p.sz)
                )
        if not alive and self._event:
            self._event.cancel()
            self._event = None


# ── Battleship Grid ──────────────────────────────────────────────────────


class BattleshipGrid(Widget):
    """Canvas-drawn 10x10 grid with touch support."""

    title = StringProperty("")
    show_ships = BooleanProperty(True)
    interactive = BooleanProperty(False)
    cell_tap_callback = ObjectProperty(None, allownone=True)

    def __init__(self, board, attacks, sunk_cells=None, **kwargs):
        self._board = board
        self._attacks = attacks
        self._sunk = set(tuple(c) for c in (sunk_cells or []))
        self._cs = dp(34)
        self._highlights = []
        self._hl_ok = True
        self._tex_cache = {}
        super().__init__(**kwargs)
        self.bind(pos=self._mark_dirty, size=self._recalc)

    def _recalc(self, *args):
        if self.width < dp(50) or self.height < dp(50):
            return
        lw = dp(16)
        th = dp(20) if self.title else 0
        lh = dp(14)
        aw = max(1, self.width - lw)
        ah = max(1, self.height - th - lh)
        self._cs = min(aw / GRID_SIZE, ah / GRID_SIZE)
        self._mark_dirty()

    def update(self, board, attacks, sunk_cells=None):
        self._board = board
        self._attacks = attacks
        self._sunk = set(tuple(c) for c in (sunk_cells or []))
        self._mark_dirty()

    def set_highlights(self, cells, valid=True):
        self._highlights = cells
        self._hl_ok = valid
        self._mark_dirty()

    def _mark_dirty(self, *args):
        Clock.schedule_once(lambda dt: self._redraw(), -1)

    def _origin(self):
        lw = dp(16)
        th = dp(20) if self.title else 0
        lh = dp(14)
        total = self._cs * GRID_SIZE
        ox = self.x + lw + (self.width - lw - total) / 2
        oy = self.y + (self.height - th - lh - total) / 2
        return ox, oy

    def _cpos(self, row, col):
        ox, oy = self._origin()
        cs = self._cs
        return ox + col * cs, oy + (GRID_SIZE - 1 - row) * cs

    def _pos2cell(self, pos):
        ox, oy = self._origin()
        cs = self._cs
        if cs <= 0:
            return None, None
        col = int((pos[0] - ox) / cs)
        row = GRID_SIZE - 1 - int((pos[1] - oy) / cs)
        if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
            return row, col
        return None, None

    def _tex(self, text, size, color):
        key = (text, size, tuple(color))
        if key not in self._tex_cache:
            cl = CoreLabel(text=text, font_size=size, font_name="Nunito", color=color)
            cl.refresh()
            self._tex_cache[key] = cl.texture
        return self._tex_cache[key]

    def _redraw(self):
        cs = self._cs
        if cs < dp(5):
            return
        self.canvas.clear()
        ox, oy = self._origin()
        total = cs * GRID_SIZE
        lh = dp(14)

        with self.canvas:
            # Ocean background
            Color(*C_OCEAN)
            Rectangle(pos=(ox, oy), size=(total, total))

            # Cells
            for row in range(GRID_SIZE):
                for col in range(GRID_SIZE):
                    x, y = self._cpos(row, col)
                    bv = self._board[row][col]
                    av = self._attacks[row][col]
                    sunk = (row, col) in self._sunk

                    # Background
                    if av == HIT:
                        Color(*(C_SHIP_SUNK if sunk else C_HIT))
                    elif self.show_ships and bv != 0:
                        Color(*(C_SHIP_SUNK if sunk else C_SHIP))
                    else:
                        Color(*C_WATER)
                    Rectangle(pos=(x + 1, y + 1), size=(cs - 2, cs - 2))

                    # Hit glow
                    if av == HIT and not sunk:
                        Color(*C_HIT_GLOW)
                        pad = cs * 0.12
                        Ellipse(
                            pos=(x - pad, y - pad),
                            size=(cs + 2 * pad, cs + 2 * pad),
                        )

                    # Miss dot
                    if av == MISS:
                        Color(*C_MISS)
                        d = cs * 0.25
                        Ellipse(
                            pos=(x + cs / 2 - d / 2, y + cs / 2 - d / 2),
                            size=(d, d),
                        )

                    # Hit cross
                    if av == HIT:
                        Color(1, 1, 1, 0.85)
                        p = cs * 0.22
                        Line(
                            points=[x + p, y + p, x + cs - p, y + cs - p],
                            width=dp(1.2),
                        )
                        Line(
                            points=[x + p, y + cs - p, x + cs - p, y + p],
                            width=dp(1.2),
                        )

            # Highlights (ship placement preview)
            for r, c in self._highlights:
                hx, hy = self._cpos(r, c)
                if self._hl_ok:
                    Color(0.2, 0.8, 0.3, 0.35)
                else:
                    Color(0.9, 0.2, 0.1, 0.35)
                Rectangle(pos=(hx + 1, hy + 1), size=(cs - 2, cs - 2))

            # Grid lines
            Color(*C_GRID_LINE)
            for i in range(GRID_SIZE + 1):
                Line(
                    points=[ox + i * cs, oy, ox + i * cs, oy + total], width=0.8
                )
                Line(
                    points=[ox, oy + i * cs, ox + total, oy + i * cs], width=0.8
                )

            # Column labels A-J
            Color(1, 1, 1, 1)
            for i, ch in enumerate("ABCDEFGHIJ"):
                t = self._tex(ch, sp(9), C_TEXT_DIM)
                Rectangle(
                    texture=t,
                    pos=(ox + i * cs + (cs - t.width) / 2, oy + total + dp(2)),
                    size=t.size,
                )

            # Row labels 1-10
            for i in range(GRID_SIZE):
                t = self._tex(str(i + 1), sp(9), C_TEXT_DIM)
                Rectangle(
                    texture=t,
                    pos=(
                        ox - t.width - dp(3),
                        oy + (GRID_SIZE - 1 - i) * cs + (cs - t.height) / 2,
                    ),
                    size=t.size,
                )

            # Title
            if self.title:
                t = self._tex(self.title, sp(11), C_ACCENT)
                Rectangle(
                    texture=t,
                    pos=(ox + (total - t.width) / 2, oy + total + lh + dp(2)),
                    size=t.size,
                )

    def on_touch_down(self, touch):
        if not self.interactive or self.disabled:
            return False
        if not self.collide_point(*touch.pos):
            return False
        row, col = self._pos2cell(touch.pos)
        if row is not None and self.cell_tap_callback:
            self.cell_tap_callback(row, col)
            return True
        return False


# ── Setup View (drag-and-drop ship placement) ───────────────────────────


class _SetupView(FloatLayout):
    """Setup phase with drag-and-drop ship placement.

    - Drag a ship from the list onto the grid to place it.
    - Drag a placed ship on the grid to reposition it.
    - Tap a placed ship on the grid to rotate it in place.
    - Drag a placed ship from the list to reposition it.
    """

    def __init__(self, screen, player, **kwargs):
        self._scr = screen
        self._player = player
        self._game = screen._game
        self._horizontal = screen._horizontal

        # Drag state
        self._dragging = False
        self._drag_idx = None
        self._drag_from_grid = False
        self._drag_origin = None
        self._touch_start = None
        self._ship_rows = []
        self._buttons = []

        super().__init__(**kwargs)
        self._build()

    def _build(self):
        main = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            padding=[dp(8), dp(4)],
            size_hint=(1, 1),
        )

        # Title
        title_bar = BoxLayout(size_hint_y=None, height=dp(28))
        tlbl = Label(
            text=f"{self._game.names[self._player]} - PLACE YOUR FLEET",
            font_name="Nunito",
            font_size=sp(14),
            bold=True,
            color=C_TEXT,
            halign="center",
            valign="middle",
        )
        tlbl.bind(size=tlbl.setter("text_size"))
        title_bar.add_widget(tlbl)
        main.add_widget(title_bar)

        # Instruction
        inst = Label(
            text="Drag ships onto the grid. Tap a placed ship to rotate.",
            font_name="Nunito",
            font_size=sp(10),
            color=C_TEXT_DIM,
            size_hint_y=None,
            height=dp(16),
            halign="center",
            valign="middle",
        )
        inst.bind(size=inst.setter("text_size"))
        main.add_widget(inst)

        # Content: grid + panel
        content = BoxLayout(orientation="horizontal", spacing=dp(16))

        self._grid = BattleshipGrid(
            board=self._game.boards[self._player],
            attacks=[[0] * GRID_SIZE for _ in range(GRID_SIZE)],
            show_ships=True,
            interactive=False,
            size_hint_x=0.55,
        )
        self._grid.title = "YOUR FLEET"
        content.add_widget(self._grid)

        self._panel_box = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
            padding=[dp(8), dp(4)],
            size_hint_x=0.45,
        )
        self._rebuild_panel()
        content.add_widget(self._panel_box)

        main.add_widget(content)
        self.add_widget(main)

        # Ghost overlay (drawn on top during drag)
        self._ghost = Widget(size_hint=(1, 1))
        self.add_widget(self._ghost)

    def _rebuild_panel(self):
        self._panel_box.clear_widgets()
        self._ship_rows = []
        self._buttons = []
        placed = self._game.placed_indices(self._player)

        for idx, ship in enumerate(SHIPS):
            is_placed = idx in placed

            row = BoxLayout(
                size_hint_y=None,
                height=dp(42),
                spacing=dp(6),
                padding=[dp(8), dp(4)],
            )
            row._ship_idx = idx

            if is_placed:
                with row.canvas.before:
                    Color(0.15, 0.35, 0.20, 0.3)
                    _r = RoundedRectangle(
                        pos=row.pos, size=row.size, radius=[dp(6)]
                    )
                row.bind(
                    pos=lambda w, p, rr=_r: setattr(rr, "pos", p),
                    size=lambda w, s, rr=_r: setattr(rr, "size", s),
                )

            dots = Label(
                text="# " * ship["size"],
                font_name="Nunito",
                font_size=sp(11),
                color=C_GREEN if is_placed else C_SHIP,
                size_hint_x=None,
                width=dp(ship["size"] * 15 + 8),
                halign="left",
                valign="middle",
            )
            dots.bind(size=dots.setter("text_size"))
            row.add_widget(dots)

            nlbl = Label(
                text=f"{ship['name']} ({ship['size']})",
                font_name="Nunito",
                font_size=sp(12),
                color=C_GREEN if is_placed else C_TEXT,
                halign="left",
                valign="middle",
            )
            nlbl.bind(size=nlbl.setter("text_size"))
            row.add_widget(nlbl)

            status = Label(
                text="OK" if is_placed else "",
                font_name="Nunito",
                font_size=sp(12),
                color=C_GREEN,
                size_hint_x=None,
                width=dp(24),
                halign="center",
                valign="middle",
            )
            row.add_widget(status)

            self._panel_box.add_widget(row)
            self._ship_rows.append(row)

        self._panel_box.add_widget(Widget())  # Spacer

        # Rotate button
        rot_text = "HORIZONTAL --" if self._horizontal else "VERTICAL |"
        rot_btn = self._scr._make_button(
            rot_text, self._on_rotate, width=dp(180), height=dp(36)
        )
        rot_btn.size_hint = (1, None)
        rot_btn.height = dp(36)
        self._panel_box.add_widget(rot_btn)
        self._buttons.append(rot_btn)

        # Randomize
        rand_btn = self._scr._make_button(
            "RANDOMIZE",
            self._on_random,
            bg=[0.18, 0.18, 0.30, 1],
            width=dp(180),
            height=dp(36),
        )
        rand_btn.size_hint = (1, None)
        rand_btn.height = dp(36)
        self._panel_box.add_widget(rand_btn)
        self._buttons.append(rand_btn)

        # Done
        all_done = self._game.all_placed(self._player)
        done_btn = self._scr._make_button(
            "DONE",
            self._on_done,
            bg=C_GREEN if all_done else [0.15, 0.15, 0.18, 0.6],
            width=dp(180),
            height=dp(38),
        )
        done_btn.size_hint = (1, None)
        done_btn.height = dp(38)
        done_btn.disabled = not all_done
        self._panel_box.add_widget(done_btn)
        self._buttons.append(done_btn)

    def _refresh(self):
        empty = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        self._grid.update(self._game.boards[self._player], empty)
        self._rebuild_panel()

    # ── Button callbacks ──

    def _on_rotate(self):
        self._horizontal = not self._horizontal
        self._rebuild_panel()

    def _on_random(self):
        for idx in range(len(SHIPS)):
            if idx in self._game.placed_indices(self._player):
                continue
            for _ in range(200):
                r = random.randint(0, GRID_SIZE - 1)
                c = random.randint(0, GRID_SIZE - 1)
                h = random.choice([True, False])
                if self._game.place_ship(self._player, idx, r, c, h):
                    break
        self._refresh()

    def _on_done(self):
        if not self._game.all_placed(self._player):
            return
        self._scr._horizontal = self._horizontal
        self._scr._on_setup_done(self._player)

    # ── Drag-and-drop touch handling ──

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False

        # Let buttons handle their own touches first
        for btn in self._buttons:
            if btn.collide_point(*touch.pos):
                return super().on_touch_down(touch)

        self._touch_start = touch.pos
        placed = self._game.placed_indices(self._player)

        # Check ship rows in the list
        for row in self._ship_rows:
            if row.collide_point(*touch.pos):
                idx = row._ship_idx
                self._drag_idx = idx
                if idx in placed:
                    # Placed ship — will pick up from grid on drag
                    self._drag_from_grid = True
                    for s in self._game.ships[self._player]:
                        if s["idx"] == idx:
                            self._drag_origin = dict(s)
                            break
                else:
                    self._drag_from_grid = False
                touch.grab(self)
                return True

        # Check grid cells for placed ships
        grow, gcol = self._grid._pos2cell(touch.pos)
        if grow is not None:
            cell = self._game.boards[self._player][grow][gcol]
            if cell != 0:
                ship_idx = cell - 1
                self._drag_idx = ship_idx
                self._drag_from_grid = True
                for s in self._game.ships[self._player]:
                    if s["idx"] == ship_idx:
                        self._drag_origin = dict(s)
                        break
                touch.grab(self)
                return True

        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current != self:
            return super().on_touch_move(touch)
        if self._drag_idx is None:
            return True

        # Start dragging after movement threshold
        if not self._dragging and self._touch_start:
            dx = abs(touch.pos[0] - self._touch_start[0])
            dy = abs(touch.pos[1] - self._touch_start[1])
            if dx + dy > dp(12):
                self._dragging = True
                # Remove ship from board if dragging a placed ship
                if self._drag_from_grid and self._drag_origin:
                    self._game.remove_ship(self._player, self._drag_idx)
                    self._refresh()

        if self._dragging:
            self._draw_ghost(touch.pos)

            # Show grid highlight preview
            grow, gcol = self._grid._pos2cell(touch.pos)
            if grow is not None:
                h = self._horizontal
                valid = self._game.can_place(
                    self._player, self._drag_idx, grow, gcol, h
                )
                cells = self._preview_cells(grow, gcol, h)
                # Auto-try other orientation if preferred doesn't fit
                if not valid:
                    alt_h = not h
                    alt_valid = self._game.can_place(
                        self._player, self._drag_idx, grow, gcol, alt_h
                    )
                    if alt_valid:
                        cells = self._preview_cells(grow, gcol, alt_h)
                        valid = True
                self._grid.set_highlights(cells, valid)
            else:
                self._grid.set_highlights([])

        return True

    def on_touch_up(self, touch):
        if touch.grab_current != self:
            return super().on_touch_up(touch)

        touch.ungrab(self)

        if self._dragging and self._drag_idx is not None:
            # Try to place at drop location
            grow, gcol = self._grid._pos2cell(touch.pos)
            placed = False
            if grow is not None:
                h = self._horizontal
                placed = self._game.place_ship(
                    self._player, self._drag_idx, grow, gcol, h
                )
                if not placed:
                    placed = self._game.place_ship(
                        self._player, self._drag_idx, grow, gcol, not h
                    )

            if not placed and self._drag_from_grid and self._drag_origin:
                # Return ship to its original position
                o = self._drag_origin
                self._game.place_ship(
                    self._player, o["idx"], o["row"], o["col"], o["h"]
                )

            self._ghost.canvas.clear()
            self._grid.set_highlights([])
            self._refresh()

            if placed:
                toast("Ship placed!", "success", 1)
            elif not self._drag_from_grid:
                toast("Drop on the grid to place", "info", 2)

        elif not self._dragging and self._drag_idx is not None:
            # Tap (no drag) on a placed ship — rotate in place
            if self._drag_from_grid:
                self._rotate_ship_in_place(self._drag_idx)

        self._dragging = False
        self._drag_idx = None
        self._drag_from_grid = False
        self._drag_origin = None
        self._touch_start = None

        return True

    # ── Drag helpers ──

    def _preview_cells(self, row, col, horizontal):
        size = SHIPS[self._drag_idx]["size"]
        cells = []
        for i in range(size):
            r = row if horizontal else row + i
            c = col + i if horizontal else col
            if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
                cells.append((r, c))
        return cells

    def _draw_ghost(self, pos):
        cs = self._grid._cs
        size = SHIPS[self._drag_idx]["size"]

        # Snap to grid cell when hovering over the grid
        grow, gcol = self._grid._pos2cell(pos)
        if grow is not None:
            gx, gy = self._grid._cpos(grow, gcol)
        else:
            gx = pos[0] - cs / 2
            gy = pos[1] - cs / 2

        self._ghost.canvas.clear()
        with self._ghost.canvas:
            # Drop shadow
            Color(0, 0, 0, 0.25)
            for i in range(size):
                if self._horizontal:
                    Rectangle(
                        pos=(gx + i * cs + dp(3), gy - dp(3)),
                        size=(cs - 2, cs - 2),
                    )
                else:
                    Rectangle(
                        pos=(gx + dp(3), gy + i * cs - dp(3)),
                        size=(cs - 2, cs - 2),
                    )
            # Ship body
            Color(0.35, 0.60, 1.0, 0.7)
            for i in range(size):
                if self._horizontal:
                    Rectangle(
                        pos=(gx + i * cs + 1, gy + 1), size=(cs - 2, cs - 2)
                    )
                else:
                    Rectangle(
                        pos=(gx + 1, gy + i * cs + 1), size=(cs - 2, cs - 2)
                    )

    def _rotate_ship_in_place(self, ship_idx):
        for s in self._game.ships[self._player]:
            if s["idx"] == ship_idx:
                row, col, h = s["row"], s["col"], s["h"]
                self._game.remove_ship(self._player, ship_idx)
                if self._game.place_ship(self._player, ship_idx, row, col, not h):
                    toast("Ship rotated!", "success", 1)
                else:
                    # Can't rotate — put it back
                    self._game.place_ship(self._player, ship_idx, row, col, h)
                    toast("Can't rotate here", "warning", 1)
                break
        self._refresh()


# ── Main Screen ──────────────────────────────────────────────────────────


class BattleshipScreen(PiHomeScreen):
    """Two-player Battleship naval combat game."""

    bg_color = ColorProperty([0.10, 0.10, 0.12, 1])
    header_color = ColorProperty([0.14, 0.14, 0.16, 1])
    text_color = ColorProperty([1, 1, 1, 1])
    muted_color = ColorProperty([1, 1, 1, 0.45])
    accent_color = ColorProperty([0.25, 0.52, 1.0, 1])
    status_color = ColorProperty([0.45, 0.45, 0.45, 1])

    status_text = StringProperty("")
    phase = StringProperty("welcome")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._game = GameState()
        self._particles = ParticleOverlay(size_hint=(1, 1))
        self._events = []
        self._horizontal = True
        self._setup_grid = None
        self._fleet_grid = None
        self._attack_grid = None
        self._has_fired = False
        self._load_config()

    # ── Config ───────────────────────────────────────────────────────────

    def _load_config(self):
        n1 = CONFIG.get("battleship", "p1_name", "Player 1").strip()
        n2 = CONFIG.get("battleship", "p2_name", "Player 2").strip()
        self._game.names[1] = n1 or "Player 1"
        self._game.names[2] = n2 or "Player 2"

    def on_config_update(self, config):
        self._load_config()
        super().on_config_update(config)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def on_enter(self, *args):
        self._load_config()
        if self._game.load() and self._game.phase != "welcome":
            # Restore names from config (may have changed)
            n1 = CONFIG.get("battleship", "p1_name", "").strip()
            n2 = CONFIG.get("battleship", "p2_name", "").strip()
            if n1:
                self._game.names[1] = n1
            if n2:
                self._game.names[2] = n2
        phase = self._game.phase
        # Don't reveal the board directly — go through handoff
        if phase == "play":
            phase = "handoff"
        self._set_phase(phase)
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        self._cancel_events()
        self._particles.clear_particles()
        self._game.save()
        return super().on_pre_leave(*args)

    # ── Scheduling helpers ───────────────────────────────────────────────

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
        self.phase = phase

        body = self.ids.get("body")
        if not body:
            return
        body.clear_widgets()

        builders = {
            "welcome": self._build_welcome,
            "setup_p1": lambda: self._build_setup(1),
            "setup_p2": lambda: self._build_setup(2),
            "handoff": self._build_handoff,
            "play": self._build_play,
            "game_over": self._build_gameover,
        }
        view = builders.get(phase, self._build_welcome)()
        body.add_widget(view)
        body.add_widget(self._particles)

        # Status text
        if phase in ("setup_p1", "setup_p2"):
            p = 1 if phase == "setup_p1" else 2
            self.status_text = f"{self._game.names[p]} placing ships"
        elif phase == "play":
            self.status_text = f"{self._game.names[self._game.turn]}'s turn"
        elif phase == "handoff":
            self.status_text = "Waiting..."
        elif phase == "game_over":
            self.status_text = "Game Over"
        else:
            self.status_text = ""

        self._game.save()

    # ── Welcome ──────────────────────────────────────────────────────────

    def _build_welcome(self):
        layout = FloatLayout()

        # Title
        title = Label(
            text="BATTLESHIP",
            font_name="Nunito",
            font_size=sp(44),
            bold=True,
            color=C_TEXT,
            size_hint=(1, None),
            height=dp(60),
            pos_hint={"center_x": 0.5, "center_y": 0.70},
        )
        layout.add_widget(title)
        # Animate title entrance
        title.opacity = 0
        title.font_size = sp(20)
        Animation(opacity=1, font_size=sp(44), d=0.6, t="out_back").start(title)

        # Subtitle
        sub = Label(
            text="A game of naval strategy",
            font_name="Nunito",
            font_size=sp(14),
            color=C_TEXT_DIM,
            size_hint=(1, None),
            height=dp(30),
            pos_hint={"center_x": 0.5, "center_y": 0.58},
        )
        layout.add_widget(sub)

        # Player names
        names = Label(
            text=f"{self._game.names[1]}  vs  {self._game.names[2]}",
            font_name="Nunito",
            font_size=sp(13),
            color=C_ACCENT,
            size_hint=(1, None),
            height=dp(30),
            pos_hint={"center_x": 0.5, "center_y": 0.49},
        )
        layout.add_widget(names)

        # NEW GAME button
        new_btn = self._make_button("NEW GAME", self._on_new_game)
        new_btn.pos_hint = {"center_x": 0.5, "center_y": 0.33}
        layout.add_widget(new_btn)

        # CONTINUE button (if valid save exists)
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE) as f:
                    d = json.load(f)
                if d.get("phase") not in ("welcome", "game_over", None):
                    cont = self._make_button(
                        "CONTINUE", self._on_continue, bg=C_GREEN
                    )
                    cont.pos_hint = {"center_x": 0.5, "center_y": 0.20}
                    layout.add_widget(cont)
        except Exception:
            pass

        # Decorative wave dots
        wave = Widget(
            size_hint=(1, None), height=dp(30), pos_hint={"x": 0, "y": 0.02}
        )
        with wave.canvas:
            Color(0.08, 0.15, 0.30, 0.4)
            for i in range(25):
                xp = dp(33) * i
                yoff = dp(4) * math.sin(i * 0.7)
                Ellipse(pos=(xp, dp(10) + yoff), size=(dp(24), dp(6)))
        layout.add_widget(wave)

        return layout

    # ── Setup ────────────────────────────────────────────────────────────

    def _build_setup(self, player):
        return _SetupView(self, player, size_hint=(1, 1))

    # ── Handoff ──────────────────────────────────────────────────────────

    def _build_handoff(self):
        layout = FloatLayout()
        player = self._game.turn

        name_lbl = Label(
            text=self._game.names[player],
            font_name="Nunito",
            font_size=sp(38),
            bold=True,
            color=C_ACCENT,
            size_hint=(1, None),
            height=dp(50),
            pos_hint={"center_x": 0.5, "center_y": 0.62},
        )
        layout.add_widget(name_lbl)

        turn_lbl = Label(
            text="YOUR TURN",
            font_name="Nunito",
            font_size=sp(16),
            color=C_TEXT_DIM,
            size_hint=(1, None),
            height=dp(30),
            pos_hint={"center_x": 0.5, "center_y": 0.52},
        )
        layout.add_widget(turn_lbl)

        ready = self._make_button(
            "I'M READY", lambda: self._start_countdown(layout), bg=C_ACCENT
        )
        ready.pos_hint = {"center_x": 0.5, "center_y": 0.35}
        layout.add_widget(ready)

        return layout

    def _start_countdown(self, container):
        # Remove all children except canvas-drawn ones
        for child in list(container.children):
            container.remove_widget(child)

        cd_lbl = Label(
            text="3",
            font_name="Nunito",
            font_size=sp(80),
            bold=True,
            color=C_ACCENT,
            size_hint=(1, 1),
        )
        container.add_widget(cd_lbl)

        counter = [3]

        def _tick(dt):
            val = counter[0]
            cd_lbl.text = str(val) if val > 0 else "GO!"
            cd_lbl.font_size = sp(100)
            cd_lbl.color = C_ACCENT if val > 0 else C_GREEN
            Animation(font_size=sp(70), d=0.6, t="out_cubic").start(cd_lbl)

            if val > 0:
                counter[0] -= 1
                self._sched(_tick, 0.8)
            else:
                self._sched(lambda dt: self._set_phase("play"), 0.5)

        _tick(0)

    # ── Play ─────────────────────────────────────────────────────────────

    def _build_play(self):
        player = self._game.turn
        opponent = 3 - player
        self._has_fired = False

        layout = BoxLayout(
            orientation="vertical", spacing=dp(2), padding=[dp(4), dp(2)]
        )

        # Info bar
        info = BoxLayout(size_hint_y=None, height=dp(24))
        info_lbl = Label(
            text=f"{self._game.names[player]}'s Turn - Select a target!",
            font_name="Nunito",
            font_size=sp(12),
            color=C_TEXT,
            halign="center",
            valign="middle",
        )
        info_lbl.bind(size=info_lbl.setter("text_size"))
        info.add_widget(info_lbl)
        layout.add_widget(info)

        # Grids
        grids = BoxLayout(orientation="horizontal", spacing=dp(8))

        # Fleet grid (your ships + enemy attacks on you)
        self._fleet_grid = BattleshipGrid(
            board=self._game.boards[player],
            attacks=self._game.attacks[opponent],
            sunk_cells=list(self._game.my_sunk_cells(player)),
            show_ships=True,
            interactive=False,
            size_hint_x=0.5,
        )
        self._fleet_grid.title = "YOUR FLEET"
        grids.add_widget(self._fleet_grid)

        # Attack grid (your attacks on enemy — don't reveal their ships)
        empty = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        self._attack_grid = BattleshipGrid(
            board=empty,
            attacks=self._game.attacks[player],
            sunk_cells=list(self._game.sunk_cells_for(player)),
            show_ships=False,
            interactive=True,
            cell_tap_callback=lambda r, c: self._on_fire(r, c),
            size_hint_x=0.5,
        )
        self._attack_grid.title = "ENEMY WATERS"
        grids.add_widget(self._attack_grid)

        layout.add_widget(grids)

        # Ship status bar
        status_bar = BoxLayout(
            size_hint_y=None, height=dp(30), spacing=dp(4), padding=[dp(8), 0]
        )
        status_bar.add_widget(
            Label(
                text="Enemy fleet:",
                font_name="Nunito",
                font_size=sp(10),
                color=C_TEXT_DIM,
                size_hint_x=None,
                width=dp(72),
                halign="right",
                valign="middle",
            )
        )
        for idx, ship in enumerate(SHIPS):
            sunk = idx in self._game.sunk[player]
            sl = Label(
                text=ship["name"][:3],
                font_name="Nunito",
                font_size=sp(10),
                color=C_RED if sunk else C_TEXT_DIM,
                size_hint_x=None,
                width=dp(42),
                halign="center",
                valign="middle",
            )
            if sunk:
                # Draw strikethrough manually with canvas
                with sl.canvas.after:
                    Color(*C_RED)
                    sl._strike = Rectangle(pos=(0, 0), size=(0, 0))

                def _upd_strike(w, *a, rect=sl._strike):
                    if w.texture_size[0] > 0:
                        rect.pos = (
                            w.center_x - w.texture_size[0] / 2,
                            w.center_y,
                        )
                        rect.size = (w.texture_size[0], dp(1))

                sl.bind(pos=_upd_strike, size=_upd_strike, texture_size=_upd_strike)
            status_bar.add_widget(sl)
        status_bar.add_widget(Widget())
        layout.add_widget(status_bar)

        return layout

    # ── Game Over ────────────────────────────────────────────────────────

    def _build_gameover(self):
        layout = FloatLayout()
        winner = self._game.winner or 1

        # Winner text
        win_lbl = Label(
            text=f"{self._game.names[winner]} WINS!",
            font_name="Nunito",
            font_size=sp(10),
            bold=True,
            color=C_GOLD,
            size_hint=(1, None),
            height=dp(60),
            pos_hint={"center_x": 0.5, "center_y": 0.72},
        )
        layout.add_widget(win_lbl)
        Animation(font_size=sp(40), d=0.7, t="out_back").start(win_lbl)

        # Stats
        for p in (1, 2):
            shots = self._game.shots.get(p, 0)
            hits = self._game.hits.get(p, 0)
            acc = f"{hits / shots * 100:.0f}%" if shots > 0 else "0%"
            is_w = p == winner
            stat = Label(
                text=f"{self._game.names[p]}:  {shots} shots  \u2022  {hits} hits  \u2022  {acc} accuracy",
                font_name="Nunito",
                font_size=sp(13),
                color=C_GOLD if is_w else C_TEXT,
                size_hint=(1, None),
                height=dp(24),
                pos_hint={"center_x": 0.5, "center_y": 0.53 - (p - 1) * 0.08},
            )
            layout.add_widget(stat)

        # New Game button
        btn = self._make_button("NEW GAME", self._on_new_game)
        btn.pos_hint = {"center_x": 0.5, "center_y": 0.25}
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
        for _ in range(3):
            x = random.uniform(body.x + dp(80), body.x + body.width - dp(80))
            y = random.uniform(body.y + dp(100), body.y + body.height - dp(60))
            color = random.choice([C_GREEN, C_ACCENT, C_GOLD, [0.9, 0.3, 0.9, 1]])
            self._particles.burst(x, y, color, count=18, speed=dp(100), life=1.0)
        self._sched(lambda dt: self._victory_burst(), 0.7)

    # ── Button helper ────────────────────────────────────────────────────

    def _make_button(self, text, callback, bg=None, width=dp(200), height=dp(44)):
        bg = list(bg or C_BTN)
        btn = BoxLayout(size_hint=(None, None), size=(width, height), padding=[dp(16), dp(8)])
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
        self._game.reset()
        self._load_config()
        self._horizontal = True
        # Delete old save
        try:
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)
        except Exception:
            pass
        self._set_phase("setup_p1")

    def _on_continue(self):
        self._game.load()
        self._load_config()
        phase = self._game.phase
        if phase == "play":
            phase = "handoff"
        self._set_phase(phase)

    def _on_setup_done(self, player):
        if not self._game.all_placed(player):
            return
        if player == 1:
            self._horizontal = True
            self._set_phase("setup_p2")
        else:
            self._game.turn = 1
            self._set_phase("handoff")

    def _on_fire(self, row, col):
        if self._has_fired:
            return
        player = self._game.turn
        result = self._game.fire(player, row, col)
        if result is None:
            toast("Already fired there!", "info", 1)
            return

        is_hit, sunk_name, game_over = result
        self._has_fired = True

        # Update attack grid visuals
        self._attack_grid.update(
            [[0] * GRID_SIZE for _ in range(GRID_SIZE)],
            self._game.attacks[player],
            list(self._game.sunk_cells_for(player)),
        )

        # Screen position of the hit cell (for effects)
        cx, cy = self._attack_grid._cpos(row, col)
        cs = self._attack_grid._cs
        px, py = cx + cs / 2, cy + cs / 2

        # Particles + floating text
        if is_hit:
            self._particles.burst(px, py, C_HIT, count=22, speed=dp(80), life=0.7)
            self._show_float("HIT!", px, py, C_RED, sp(22))
            if sunk_name:
                self._sched(
                    lambda dt, n=sunk_name: self._show_float(
                        f"{n} SUNK!", px, py + dp(30), C_GOLD, sp(16)
                    ),
                    0.4,
                )
                self._sched(
                    lambda dt: self._particles.burst(
                        px, py, C_GOLD, count=30, speed=dp(120), life=1.0
                    ),
                    0.3,
                )
        else:
            self._show_float("MISS", px, py, C_TEXT_DIM, sp(16))

        # Save turn change immediately (in case user leaves before transition)
        if not game_over:
            self._game.turn = 3 - self._game.turn
        self._game.save()

        # Delayed transition
        if game_over:
            self._sched(lambda dt: self._set_phase("game_over"), 2.0)
        else:
            self._sched(lambda dt: self._set_phase("handoff"), 2.5)

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
            pos=(x - dp(55), y),
            size_hint=(None, None),
            size=(dp(110), dp(30)),
            halign="center",
            valign="middle",
        )
        lbl.text_size = lbl.size
        body.add_widget(lbl)
        anim = Animation(y=y + dp(60), opacity=0, d=1.5, t="out_quad")
        anim.bind(on_complete=lambda *a: body.remove_widget(lbl) if lbl.parent else None)
        anim.start(lbl)

    # ── Rotary Encoder ───────────────────────────────────────────────────

    def on_rotary_pressed(self):
        return True

    def on_rotary_turn(self, direction, button_pressed):
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True
