"""CocktailScreen — browse and search TheCocktailDB for cocktail recipes.

Designed for the Raspberry Pi 7" v1 touchscreen (800 × 480).

Layout
------
Left panel (255 dp)  Search row (dp 52, with hamburger gap + search + dice)
                     + category chips + scrollable results list
Right panel (rest)   Drink image + name + badges + ingredients + instructions

Config
------
Section: cocktaildb
Key:     api_key    (default "1" — free tier; set a paid key for full access)
"""

import json
import os
import time
import urllib.parse
from threading import Thread

from kivy.clock import Clock
from kivy.graphics import Color as KColor, Ellipse, Rectangle, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

try:
    import requests as _requests
except ImportError:
    _requests = None

from interface.pihomescreen import PiHomeScreen
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/Cocktail/cocktail.kv")

# ── Design tokens ─────────────────────────────────────────────────────────────

_BG       = [0.07, 0.06, 0.05, 1.0]          # very dark warm almost-black
_PANEL_BG = [0.11, 0.09, 0.08, 1.0]          # slightly lighter for left panel
_ACCENT   = [0.95, 0.67, 0.20, 1.0]          # warm amber / gold
_TEXT     = [1.00, 0.96, 0.90, 1.0]          # warm white
_MUTED    = [1.00, 0.96, 0.90, 0.45]
_DIVIDER  = [1.00, 0.96, 0.90, 0.07]

_LIST_W   = dp(255)     # left panel width — leaves ≈545 dp for detail
_ITEM_H   = dp(56)      # list row height

# CocktailDB free base URL — replace "1" with a paid key if configured
_API_BASE   = "https://www.thecocktaildb.com/api/json/v1/{key}/"
_CACHE_FILE = "cache/cocktail_cache.json"
_FAV_FILE   = "cache/cocktail_favorites.json"
_CACHE_TTL  = 86_400    # 24 hours

# Category quick-filters shown as chips.
# "__favorites__" is a sentinel that shows the locally-saved favourites list.
_CATEGORIES = [
    ("All",      None),
    ("Saved",    "__favorites__"),
    ("Cocktail", "Cocktail"),
    ("Shot",     "Shot"),
    ("Beer",     "Beer"),
    ("Coffee",   "Coffee / Tea"),
]


# ── Cache ─────────────────────────────────────────────────────────────────────

class _Cache:
    def __init__(self, path: str):
        self._path = path
        self._data: dict = {}
        self._load()

    def _load(self):
        try:
            with open(self._path) as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._data, f)
        except Exception as e:
            PIHOME_LOGGER.error(f"Cocktail cache save failed: {e}")

    def get(self, key: str):
        entry = self._data.get(key)
        if entry and time.time() - entry.get("ts", 0) < _CACHE_TTL:
            return entry["data"]
        return None

    def put(self, key: str, data):
        self._data[key] = {"ts": time.time(), "data": data}
        self._save()


COCKTAIL_CACHE = _Cache(_CACHE_FILE)


# ── Favourites ────────────────────────────────────────────────────────────────

class _Favourites:
    """Persists favourited drinks as {id: {"name": str, "thumb": str}}.

    Automatically migrates the old list-of-IDs format on first load.
    """

    def __init__(self, path: str):
        self._path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self):
        try:
            with open(self._path) as f:
                raw = json.load(f)
            # Migrate old format (plain list of ID strings)
            if isinstance(raw, list):
                self._data = {i: {"name": "", "thumb": ""} for i in raw}
            else:
                self._data = dict(raw)
        except Exception:
            self._data = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._data, f)
        except Exception as e:
            PIHOME_LOGGER.error(f"Cocktail favourites save failed: {e}")

    def toggle(self, drink_id: str, name: str = "", thumb: str = "") -> bool:
        if drink_id in self._data:
            del self._data[drink_id]
        else:
            self._data[drink_id] = {"name": name, "thumb": thumb}
        self._save()
        return drink_id in self._data

    def is_fav(self, drink_id: str) -> bool:
        return drink_id in self._data

    def all_drinks(self) -> list[dict]:
        """Return slim drink dicts compatible with _populate_list."""
        return [
            {"idDrink": did, "strDrink": meta["name"], "strDrinkThumb": meta["thumb"]}
            for did, meta in self._data.items()
        ]


COCKTAIL_FAVS = _Favourites(_FAV_FILE)


# ── API ───────────────────────────────────────────────────────────────────────

class CocktailAPI:
    """Thin async wrapper around TheCocktailDB JSON API."""

    @staticmethod
    def _base() -> str:
        key = CONFIG.get("cocktaildb", "api_key", "1").strip() or "1"
        return _API_BASE.format(key=key)

    @staticmethod
    def _get_async(url: str, cache_key: str | None, callback):
        if cache_key:
            hit = COCKTAIL_CACHE.get(cache_key)
            if hit is not None:
                Clock.schedule_once(lambda dt: callback(hit), 0)
                return

        def _run():
            if not _requests:
                Clock.schedule_once(lambda dt: callback(None), 0)
                return
            try:
                r = _requests.get(url, timeout=8)
                data = r.json()
                # Only cache responses that actually contain drinks.
                # Caching null/empty responses would permanently poison the
                # cache key, causing every subsequent identical search to
                # return "no results" even after the network is healthy.
                if cache_key and (data or {}).get("drinks"):
                    COCKTAIL_CACHE.put(cache_key, data)
                Clock.schedule_once(lambda dt: callback(data), 0)
            except Exception as e:
                PIHOME_LOGGER.error(f"Cocktail API error: {e}")
                Clock.schedule_once(lambda dt: callback(None), 0)

        Thread(target=_run, daemon=True).start()

    @staticmethod
    def search(query: str, callback):
        """Search drinks by name. Returns list of slim drink objects."""
        q = query.strip().lower()
        # Properly encode spaces and special chars so "old fashioned" works
        q_enc = urllib.parse.quote(q)
        url = CocktailAPI._base() + f"search.php?s={q_enc}"

        def _wrap(data):
            callback((data or {}).get("drinks") or [])

        CocktailAPI._get_async(url, f"search:{q}", _wrap)

    @staticmethod
    def get_detail(drink_id: str, callback):
        """Fetch full drink detail by ID. Returns a single drink dict or None."""
        url = CocktailAPI._base() + f"lookup.php?i={drink_id}"

        def _wrap(data):
            drinks = (data or {}).get("drinks") or []
            callback(drinks[0] if drinks else None)

        CocktailAPI._get_async(url, f"detail:{drink_id}", _wrap)

    @staticmethod
    def get_random(callback):
        """Fetch one random drink. Never cached."""
        url = CocktailAPI._base() + "random.php"

        def _wrap(data):
            drinks = (data or {}).get("drinks") or []
            callback(drinks[0] if drinks else None)

        CocktailAPI._get_async(url, None, _wrap)

    @staticmethod
    def filter_category(category: str, callback):
        """Filter drinks by category. Returns slim list."""
        url = CocktailAPI._base() + f"filter.php?c={category}"

        def _wrap(data):
            callback((data or {}).get("drinks") or [])

        CocktailAPI._get_async(url, f"cat:{category}", _wrap)


# ── CategoryChip ──────────────────────────────────────────────────────────────

class CategoryChip(Widget):
    """Pill-shaped filter chip for the category row."""

    label      = StringProperty("")
    selected   = BooleanProperty(False)
    on_pressed = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.height    = dp(26)
        self.pos_hint  = {"center_y": 0.5}

        self._lbl = Label(
            text=self.label,
            font_name="Nunito",
            font_size="11sp",
            halign="center",
            valign="middle",
        )
        self._lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.bind(
            label=self._on_label,
            selected=self._redraw,
            pos=self._sync,
            size=self._sync,
        )
        self.add_widget(self._lbl)
        Clock.schedule_once(self._on_label, 0)

    def _on_label(self, *_):
        self._lbl.text = self.label
        # Measure width from character count — rough but fast, no texture needed
        self.width = len(self.label) * dp(7.5) + dp(20)
        self._sync()

    def _sync(self, *_):
        self._lbl.pos  = self.pos
        self._lbl.size = self.size
        self._redraw()

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            if self.selected:
                KColor(rgba=_ACCENT)
                RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(13)])
                self._lbl.color = [0.07, 0.06, 0.05, 1.0]   # dark text on amber
            else:
                KColor(rgba=[1, 1, 1, 0.09])
                RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(13)])
                self._lbl.color = list(_MUTED)

    def on_touch_down(self, touch):
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self.on_pressed:
            self.on_pressed()
            return True
        return False


# ── DrinkListItem ─────────────────────────────────────────────────────────────

class DrinkListItem(Widget):
    """A single row in the search-results list."""

    drink_id   = StringProperty("")
    drink_name = StringProperty("")
    thumb_url  = StringProperty("")
    selected   = BooleanProperty(False)
    on_pressed = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = _ITEM_H

        # Thumbnail
        self._thumb = AsyncImage(
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None),
            size=(dp(38), dp(38)),
        )
        # Name label
        self._name_lbl = Label(
            font_name="Nunito",
            font_size="12sp",
            color=list(_TEXT),
            halign="left",
            valign="middle",
        )
        self._name_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))

        self.add_widget(self._thumb)
        self.add_widget(self._name_lbl)

        self.bind(
            pos=self._layout,
            size=self._layout,
            selected=self._draw_bg,
            thumb_url=lambda _, v: setattr(self._thumb, "source", v + "/preview" if v else ""),
            drink_name=lambda _, v: setattr(self._name_lbl, "text", v),
        )
        Clock.schedule_once(lambda dt: (
            setattr(self._thumb, "source", self.thumb_url + "/preview" if self.thumb_url else ""),
            setattr(self._name_lbl, "text", self.drink_name),
            self._layout(),
        ), 0)

    def _layout(self, *_):
        pad = dp(10)
        th  = dp(38)
        cy  = self.center_y

        self._thumb.pos  = (self.x + pad, cy - th / 2)
        self._thumb.size = (th, th)

        name_x = self.x + pad + th + dp(10)
        self._name_lbl.pos  = (name_x, self.y)
        self._name_lbl.size = (self.width - name_x + self.x - pad, self.height)
        self._draw_bg()

    def _draw_bg(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            if self.selected:
                KColor(rgba=[*_ACCENT[:3], 0.12])
                RoundedRectangle(
                    pos=(self.x + dp(4), self.y + dp(2)),
                    size=(self.width - dp(8), self.height - dp(4)),
                    radius=[dp(6)],
                )
                KColor(rgba=_ACCENT)
                RoundedRectangle(
                    pos=(self.x + dp(4), self.y + dp(6)),
                    size=(dp(3), self.height - dp(12)),
                    radius=[dp(2)],
                )
            # Bottom separator
            KColor(rgba=_DIVIDER)
            Rectangle(
                pos=(self.x + dp(56), self.y),
                size=(self.width - dp(56), dp(1)),
            )

    def on_touch_down(self, touch):
        return self.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self.on_pressed:
            self.on_pressed(self.drink_id)
            return True
        return False


# ── CocktailScreen ────────────────────────────────────────────────────────────

class CocktailScreen(PiHomeScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected_id: str | None = None
        self._category_idx: int = 0
        self._result_items: list[DrinkListItem] = []

        # Widget refs (populated in _build_ui)
        self._search_input   = None
        self._results_box    = None
        self._detail_area    = None
        self._chips: list[CategoryChip] = []

        Clock.schedule_once(self._build_ui, 0)

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        CONFIG.get("cocktaildb", "api_key", "1")   # ensures key exists in ini

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, *_):
        self._load_config()
        self.clear_widgets()

        # Root is horizontal: left panel (fixed width) + vertical rule + detail
        root = BoxLayout(orientation="horizontal")
        with root.canvas.before:
            KColor(rgba=_BG)
            _r = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda _, v: setattr(_r, "pos", v),
            size=lambda _, v: setattr(_r, "size", v),
        )

        # ── Left panel ────────────────────────────────────────────────────────
        left = BoxLayout(
            orientation="vertical",
            size_hint=(None, 1),
            width=_LIST_W,
            spacing=0,
        )
        with left.canvas.before:
            KColor(rgba=_PANEL_BG)
            _lp = Rectangle(pos=left.pos, size=left.size)
        left.bind(
            pos=lambda _, v: setattr(_lp, "pos", v),
            size=lambda _, v: setattr(_lp, "size", v),
        )

        # ── Search row (top of left panel) ────────────────────────────────────
        # dp(58) left spacer clears the hamburger button that floats above.
        # The search field then fills the remaining width; dice button is fixed
        # on the right edge — everything stays within _LIST_W.
        search_row = BoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(52),
            padding=[0, dp(6), dp(4), dp(6)],
            spacing=0,
        )

        # Hamburger clearance — transparent gap
        search_row.add_widget(Widget(size_hint=(None, 1), width=dp(58)))

        # Inline import avoids circular dependency issues at module load time
        from components.Keyboard.keyboard import PiTextInput

        # Dark rounded search wrapper — fills the remaining width before dice
        ti_wrapper = BoxLayout(size_hint=(1, 1))

        def _ti_bg(*_):
            ti_wrapper.canvas.before.clear()
            with ti_wrapper.canvas.before:
                KColor(rgba=[0.18, 0.15, 0.12, 1.0])
                RoundedRectangle(
                    pos=ti_wrapper.pos, size=ti_wrapper.size, radius=[dp(8)]
                )

        ti_wrapper.bind(pos=_ti_bg, size=_ti_bg)
        Clock.schedule_once(lambda dt: _ti_bg(), 0)

        ti = PiTextInput(hint_text="Search cocktails…", multiline=False)
        ti.background_color = (0, 0, 0, 0)   # transparent — wrapper paints bg
        # The PiHomeKeyboard ↵ key sets focus=False but does NOT fire
        # on_text_validate. Hook focus→False to trigger the search instead.
        ti.bind(focus=lambda inst, focused: self._do_search(inst.text) if not focused and inst.text.strip() else None)
        self._search_input = ti
        ti_wrapper.add_widget(ti)
        search_row.add_widget(ti_wrapper)

        # Dice / random button — fixed width, stays inside the left panel
        rand_lbl = Label(
            text="\ue865",
            font_name="MaterialIcons",
            font_size="20sp",
            color=list(_MUTED),
            size_hint=(None, 1),
            width=dp(36),
            halign="center",
            valign="middle",
        )
        rand_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        rand_lbl.bind(on_touch_up=lambda w, t: self._do_random() if w.collide_point(*t.pos) else None)
        search_row.add_widget(rand_lbl)

        left.add_widget(search_row)

        # Category chips ───────────────────────────────────────────────────────
        chips_sv = ScrollView(
            size_hint=(1, None),
            height=dp(38),
            do_scroll_x=True,
            do_scroll_y=False,
            bar_width=0,
        )
        chips_box = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            spacing=dp(6),
            padding=[dp(10), dp(5), dp(10), dp(5)],
        )
        chips_box.bind(minimum_width=chips_box.setter("width"))
        self._chips = []
        for i, (lbl_text, _) in enumerate(_CATEGORIES):
            ch = CategoryChip(label=lbl_text, selected=(i == 0))
            ch.on_pressed = (lambda idx=i: lambda: self._on_category(idx))()
            self._chips.append(ch)
            chips_box.add_widget(ch)
        chips_sv.add_widget(chips_box)
        left.add_widget(chips_sv)

        left.add_widget(_h_rule())

        # Results list ─────────────────────────────────────────────────────────
        results_sv = ScrollView(size_hint=(1, 1))
        results_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=0,
        )
        results_box.bind(minimum_height=results_box.setter("height"))
        self._results_box = results_box
        results_sv.add_widget(results_box)
        left.add_widget(results_sv)

        root.add_widget(left)

        # Vertical divider between panels ─────────────────────────────────────
        root.add_widget(_v_rule())

        # ── Right panel (detail) ──────────────────────────────────────────────
        detail_area = BoxLayout(orientation="vertical")
        self._detail_area = detail_area
        root.add_widget(detail_area)

        self.add_widget(root)

        self._show_empty_list()
        self._show_empty_detail()

    # ── Left panel helpers ────────────────────────────────────────────────────

    def _show_empty_list(self):
        if not self._results_box:
            return
        self._results_box.clear_widgets()
        self._result_items.clear()
        self._results_box.add_widget(Widget(size_hint_y=None, height=dp(50)))
        self._results_box.add_widget(_muted_label("Search or pick a category", "12sp"))

    def _show_loading_list(self):
        if not self._results_box:
            return
        self._results_box.clear_widgets()
        self._result_items.clear()
        self._results_box.add_widget(Widget(size_hint_y=None, height=dp(60)))
        self._results_box.add_widget(_muted_label("\ue863", "28sp", font="MaterialIcons"))

    def _populate_list(self, drinks: list):
        if not self._results_box:
            return
        self._results_box.clear_widgets()
        self._result_items.clear()

        if not drinks:
            self._results_box.add_widget(Widget(size_hint_y=None, height=dp(50)))
            self._results_box.add_widget(_muted_label("No results found", "12sp"))
            return

        for d in drinks:
            item = DrinkListItem(
                drink_id=d.get("idDrink", ""),
                drink_name=d.get("strDrink", ""),
                thumb_url=d.get("strDrinkThumb", ""),
                selected=(d.get("idDrink") == self._selected_id),
            )
            item.on_pressed = self._on_item_tap
            self._result_items.append(item)
            self._results_box.add_widget(item)

    # ── Right panel helpers ───────────────────────────────────────────────────

    def _show_empty_detail(self):
        if not self._detail_area:
            return
        self._detail_area.clear_widgets()
        wrap = BoxLayout(orientation="vertical")
        wrap.add_widget(Widget())
        wrap.add_widget(_muted_label("\ue544", "52sp", font="MaterialIcons"))   # local_bar
        wrap.add_widget(_muted_label("Select a cocktail", "14sp"))
        wrap.add_widget(_muted_label("Search or browse by category", "11sp", alpha=0.28))
        wrap.add_widget(Widget())
        self._detail_area.add_widget(wrap)

    def _show_loading_detail(self):
        if not self._detail_area:
            return
        self._detail_area.clear_widgets()
        wrap = BoxLayout(orientation="vertical")
        wrap.add_widget(Widget())
        wrap.add_widget(_muted_label("\ue863", "36sp", font="MaterialIcons"))
        wrap.add_widget(Widget())
        self._detail_area.add_widget(wrap)

    def _show_detail(self, drink: dict):
        if not self._detail_area or not drink:
            self._show_empty_detail()
            return
        self._detail_area.clear_widgets()

        drink_id     = drink.get("idDrink", "")
        name         = drink.get("strDrink", "Unknown")
        category     = drink.get("strCategory", "")
        alcoholic    = drink.get("strAlcoholic", "")
        thumb        = drink.get("strDrinkThumb", "")
        glass        = drink.get("strGlass", "")
        instructions = (drink.get("strInstructions") or "").strip()

        # Parse ingredients (up to 15 slots)
        ingredients: list[tuple[str, str]] = []
        for n in range(1, 16):
            ing  = (drink.get(f"strIngredient{n}") or "").strip()
            meas = (drink.get(f"strMeasure{n}")    or "").strip()
            if ing:
                ingredients.append((meas, ing))

        container = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(10), dp(18), dp(10)],
            spacing=dp(6),
        )

        # Drink image ──────────────────────────────────────────────────────────
        img_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(160),
        )
        img_row.add_widget(Widget())
        img = AsyncImage(
            source=thumb,
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None),
            size=(dp(140), dp(140)),
        )
        img.pos_hint = {"center_y": 0.5}
        img_row.add_widget(img)
        img_row.add_widget(Widget())
        container.add_widget(img_row)

        # Name + favourite heart ───────────────────────────────────────────────
        name_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34),
        )
        name_lbl = Label(
            text=name,
            font_name="Nunito",
            font_size="16sp",
            bold=True,
            color=list(_TEXT),
            halign="left",
            valign="middle",
        )
        name_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        name_row.add_widget(name_lbl)

        heart = Label(
            text="\ue87d" if COCKTAIL_FAVS.is_fav(drink_id) else "\ue87e",
            font_name="MaterialIcons",
            font_size="20sp",
            color=list(_ACCENT) if COCKTAIL_FAVS.is_fav(drink_id) else list(_MUTED),
            size_hint=(None, 1),
            width=dp(34),
            halign="center",
            valign="middle",
        )
        heart.bind(size=lambda w, s: setattr(w, "text_size", s))

        def _toggle_fav(widget, touch):
            if not widget.collide_point(*touch.pos):
                return False
            now = COCKTAIL_FAVS.toggle(drink_id, name=name, thumb=thumb)
            widget.text  = "\ue87d" if now else "\ue87e"
            widget.color = list(_ACCENT) if now else list(_MUTED)
            # If the Saved chip is active, refresh the list immediately
            _, active_cat = _CATEGORIES[self._category_idx]
            if active_cat == "__favorites__":
                self._show_favorites()
            return True

        heart.bind(on_touch_up=_toggle_fav)
        name_row.add_widget(heart)
        container.add_widget(name_row)

        # Badges (category + alcoholic) ────────────────────────────────────────
        badge_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(22),
            spacing=dp(6),
        )
        for badge_text in filter(None, [category, alcoholic]):
            badge_row.add_widget(_badge(badge_text))
        badge_row.add_widget(Widget())   # left-align badges
        container.add_widget(badge_row)

        container.add_widget(_h_rule())

        # Ingredients + instructions in a single scrollable area ───────────────
        detail_sv = ScrollView(size_hint_y=1)
        inner     = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[0, dp(4), 0, dp(12)],
            spacing=dp(2),
        )
        inner.bind(minimum_height=inner.setter("height"))

        for meas, ing in ingredients:
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(26),
                spacing=dp(8),
            )
            meas_lbl = Label(
                text=meas,
                font_name="Nunito",
                font_size="11sp",
                color=[*_ACCENT[:3], 0.75],
                size_hint=(None, 1),
                width=dp(80),
                halign="right",
                valign="middle",
            )
            meas_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            ing_lbl = Label(
                text=ing,
                font_name="Nunito",
                font_size="12sp",
                color=list(_TEXT),
                halign="left",
                valign="middle",
            )
            ing_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            row.add_widget(meas_lbl)
            row.add_widget(ing_lbl)
            inner.add_widget(row)

        if instructions:
            inner.add_widget(Widget(size_hint_y=None, height=dp(8)))
            inner.add_widget(_h_rule_widget(dp(1)))
            inner.add_widget(Widget(size_hint_y=None, height=dp(4)))

            inst_lbl = Label(
                text=instructions,
                font_name="Nunito",
                font_size="11sp",
                color=list(_MUTED),
                halign="left",
                valign="top",
                size_hint_y=None,
                height=dp(20),
            )

            def _inst_resize(widget, size):
                widget.text_size = (size[0], None)
                widget.texture_update()
                widget.height = widget.texture_size[1] + dp(6)

            inst_lbl.bind(size=_inst_resize)
            inner.add_widget(inst_lbl)

        if glass:
            gl = Label(
                text=f"Serve in: {glass}",
                font_name="Nunito",
                font_size="10sp",
                color=[*_MUTED[:3], 0.30],
                size_hint_y=None,
                height=dp(20),
                halign="left",
            )
            gl.bind(size=lambda w, s: setattr(w, "text_size", s))
            inner.add_widget(Widget(size_hint_y=None, height=dp(6)))
            inner.add_widget(gl)

        detail_sv.add_widget(inner)
        container.add_widget(detail_sv)
        self._detail_area.add_widget(container)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_search(self, query: str):
        query = query.strip()
        if not query:
            return
        self._show_loading_list()
        CocktailAPI.search(query, self._populate_list)

    def _do_random(self):
        self._show_loading_detail()

        def _got(drink):
            if drink:
                self._selected_id = drink.get("idDrink")
                self._show_detail(drink)
            else:
                self._show_empty_detail()

        CocktailAPI.get_random(_got)

    def _on_category(self, idx: int):
        self._category_idx = idx
        for i, ch in enumerate(self._chips):
            ch.selected = (i == idx)
        _, cat = _CATEGORIES[idx]
        if cat is None:
            self._show_empty_list()
        elif cat == "__favorites__":
            self._show_favorites()
        else:
            self._show_loading_list()
            CocktailAPI.filter_category(cat, self._populate_list)

    def _show_favorites(self):
        """Populate the results list from locally-stored favourites (no network)."""
        if not self._results_box:
            return
        drinks = COCKTAIL_FAVS.all_drinks()
        if drinks:
            self._populate_list(drinks)
        else:
            self._results_box.clear_widgets()
            self._result_items.clear()
            self._results_box.add_widget(Widget(size_hint_y=None, height=dp(50)))
            self._results_box.add_widget(_muted_label("\ue87e", "28sp", font="MaterialIcons"))
            self._results_box.add_widget(_muted_label("No saved cocktails yet", "12sp"))

    def _on_item_tap(self, drink_id: str):
        if drink_id == self._selected_id:
            return
        self._selected_id = drink_id
        for item in self._result_items:
            item.selected = (item.drink_id == drink_id)
        self._show_loading_detail()
        CocktailAPI.get_detail(
            drink_id,
            lambda d: self._show_detail(d) if d else self._show_empty_detail(),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, *args):
        self._load_config()
        super().on_enter(*args)

    def on_config_update(self, config):
        self._load_config()
        super().on_config_update(config)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _muted_label(
    text: str,
    font_size: str = "12sp",
    font: str = "Nunito",
    alpha: float = 0.45,
) -> Label:
    lbl = Label(
        text=text,
        font_name=font,
        font_size=font_size,
        color=[*_MUTED[:3], alpha],
        size_hint_y=None,
        height=dp(40),
        halign="center",
        valign="middle",
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
    return lbl


def _h_rule() -> Widget:
    """Full-width 1 dp horizontal rule."""
    return _h_rule_widget(dp(1))


def _h_rule_widget(h: float) -> Widget:
    w = Widget(size_hint_y=None, height=h)
    with w.canvas:
        KColor(rgba=_DIVIDER)
        _r = Rectangle(pos=w.pos, size=w.size)
    w.bind(
        pos=lambda _, v: setattr(_r, "pos", v),
        size=lambda _, v: setattr(_r, "size", v),
    )
    return w


def _v_rule() -> Widget:
    """Full-height 1 dp vertical rule."""
    v = Widget(size_hint=(None, 1), width=dp(1))
    with v.canvas:
        KColor(rgba=_DIVIDER)
        _r = Rectangle(pos=v.pos, size=v.size)
    v.bind(
        pos=lambda _, v2: setattr(_r, "pos", v2),
        size=lambda _, v2: setattr(_r, "size", v2),
    )
    return v


def _badge(text: str) -> Widget:
    """Small amber pill label for category/alcoholic badges."""
    lbl = Label(
        text=text,
        font_name="Nunito",
        font_size="10sp",
        size_hint=(None, None),
        height=dp(20),
        halign="center",
        valign="middle",
    )
    lbl.texture_update()
    lbl.width = max(lbl.texture_size[0] + dp(14), dp(30))
    lbl.color = [*_ACCENT[:3], 0.90]

    def _draw(*_):
        lbl.canvas.before.clear()
        with lbl.canvas.before:
            KColor(rgba=[*_ACCENT[:3], 0.14])
            RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[dp(10)])

    lbl.bind(pos=_draw, size=_draw)
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    Clock.schedule_once(lambda dt: _draw(), 0)
    return lbl
