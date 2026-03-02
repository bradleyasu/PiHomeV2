from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from composites.HomeAssistant.hadevicecard import (  # noqa — registers kv rules
    HACoverCard, HALightCard, HATriggerCard, HAToggleCard,
    HAClimateCard, HAMediaCard,
    make_ha_card, load_ha_favorites,
)
from interface.pihomescreen import PiHomeScreen
from services.homeassistant.homeassistant import HOME_ASSISTANT, HomeAssistantListener
from theme import theme as t

Builder.load_file("./screens/HomeAssistantScreen/HomeAssistantScreen.kv")

# ─────────────────────────────────────────────────────────────────────────────
# Domain groups: (section_label, [domains], card_class, row_height)
# ─────────────────────────────────────────────────────────────────────────────
GROUPS = [
    ("LIGHTS",             ["light"],                           HALightCard,   dp(108)),
    ("SWITCHES & DEVICES", ["switch", "input_boolean", "fan"], HAToggleCard,  dp(72)),
    ("COVERS",             ["cover"],                           HACoverCard,   dp(72)),
    ("SCENES & SCRIPTS",   ["scene", "script"],                 HATriggerCard, dp(72)),
    ("THERMOSTATS",        ["climate"],                         HAClimateCard, dp(120)),
    ("MEDIA PLAYERS",      ["media_player"],                    HAMediaCard,   dp(130)),
]


class HomeAssistantScreen(PiHomeScreen):

    bg_color     = ColorProperty([0, 0, 0, 1])
    header_color = ColorProperty([0, 0, 0, 1])
    text_color   = ColorProperty([1, 1, 1, 1])
    accent_color = ColorProperty([0.36, 0.67, 1.0, 1.0])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Theme colours
        theme = t.Theme()
        self.bg_color     = theme.get_color(t.Theme.BACKGROUND_PRIMARY)
        self.header_color = theme.get_color(t.Theme.BACKGROUND_SECONDARY)
        self.text_color   = theme.get_color(t.Theme.TEXT_PRIMARY)
        self.accent_color = theme.get_color(t.Theme.ALERT_INFO)

        self._card_registry: dict = {}
        self._focusable_cards: list = []   # ordered flat list for rotary navigation
        self._focus_idx: int = -1

        # Register HA state listener
        self._listener = HomeAssistantListener(self._on_state_change)
        HOME_ASSISTANT.add_listener(self._listener)

    # ── Screen lifecycle ──────────────────────────────────────────────────────

    def on_pre_enter(self, *args):
        # Show the screen instantly with a loading message, then build on the next frame.
        self._show_loading()
        if HOME_ASSISTANT.current_states:
            Clock.schedule_once(
                lambda dt: self._build_entity_list(HOME_ASSISTANT.current_states), 0
            )
        else:
            Clock.schedule_once(lambda dt: self.refresh(), 0)
        return super().on_pre_enter(*args)

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self):
        """Fetch all HA states in a background thread, then rebuild the UI."""
        def _fetch():
            states = HOME_ASSISTANT.get_all_states()
            if states is not None:
                Clock.schedule_once(lambda dt: self._build_entity_list(states), 0)

        Thread(target=_fetch, daemon=True).start()

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _show_loading(self):
        """Replace scroll_content with a single centred loading label."""
        scroll_content = self.ids.get('scroll_content')
        if scroll_content is None:
            return
        scroll_content.clear_widgets()
        lbl = Label(
            text='Loading...',
            font_name='Nunito',
            font_size='16sp',
            color=(self.text_color[0], self.text_color[1], self.text_color[2], 0.45),
            size_hint_y=None,
            height=dp(60),
            halign='center',
            valign='middle',
        )
        lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        scroll_content.add_widget(lbl)
    def _section_label(self, text: str) -> Label:
        lbl = Label(
            text=text,
            font_name='Nunito',
            font_size='11sp',
            bold=True,
            color=(self.text_color[0], self.text_color[1], self.text_color[2], 0.45),
            halign='left',
            valign='middle',
            size_hint_y=None,
            height=dp(28),
        )
        lbl.bind(size=lambda w, s: setattr(w, 'text_size', (s[0], None)))
        return lbl

    def _make_grid(self, row_h: float) -> GridLayout:
        grid = GridLayout(
            cols=2,
            row_force_default=True,
            row_default_height=row_h,
            size_hint_y=None,
            spacing=dp(6),
        )
        grid.bind(minimum_height=grid.setter('height'))
        return grid

    def _build_entity_list(self, states: dict):
        """Populate scroll_content with section headers and 2-column device grids."""
        scroll_content = self.ids.get('scroll_content')
        if scroll_content is None:
            return

        scroll_content.clear_widgets()
        self._card_registry.clear()

        def _add_card(entity_id, state_dict, grid):
            card = make_ha_card(entity_id, state_dict)
            if card is None:
                return
            card.size_hint = (1, 1)
            card.bind(is_favorite=self._on_favorite_changed)
            card._focus_callback = self._set_focus_card
            grid.add_widget(card)
            self._card_registry[entity_id] = card

        # ── Favorites section ──────────────────────────────────────────────────────
        fav_ids = [eid for eid in sorted(load_ha_favorites()) if eid in states]
        if fav_ids:
            scroll_content.add_widget(self._section_label("FAVORITES"))
            grid = self._make_grid(dp(108))   # dp(108) fits light cards with sliders
            for eid in fav_ids:
                _add_card(eid, states[eid], grid)
            if len(fav_ids) % 2 == 1:
                grid.add_widget(Widget())
            scroll_content.add_widget(grid)
            scroll_content.add_widget(Widget(size_hint_y=None, height=dp(8)))

        # ── Domain groups (skip already-shown favorites) ───────────────────────────
        for section_title, domains, card_cls, row_h in GROUPS:
            entities = [
                (eid, sdict)
                for eid, sdict in states.items()
                if any(eid.startswith(d + '.') for d in domains)
                and eid not in self._card_registry   # skip favorited
            ]
            if not entities:
                continue

            scroll_content.add_widget(self._section_label(section_title))
            grid = self._make_grid(row_h)

            for entity_id, state_dict in entities:
                _add_card(entity_id, state_dict, grid)

            # Pad odd column with invisible spacer
            if len(entities) % 2 == 1:
                grid.add_widget(Widget())

            scroll_content.add_widget(grid)
            scroll_content.add_widget(Widget(size_hint_y=None, height=dp(8)))

        # Build focusable list in GROUPS order and select first card
        self._focusable_cards = list(self._card_registry.values())
        self._focus_idx = -1
        if self._focusable_cards:
            self._set_focus(0)

    def _on_state_change(self, entity_id: str, state_str: str, state_dict: dict):
        """Called by HA WebSocket listener (possibly on a background thread)."""
        card = self._card_registry.get(entity_id)
        if card is not None:
            attributes = state_dict.get("attributes", {}) if isinstance(state_dict, dict) else {}
            Clock.schedule_once(lambda dt: card.update_state(state_str, attributes), 0)

    def _on_favorite_changed(self, card, value):
        """Re-build the list whenever a card is starred or un-starred."""
        if HOME_ASSISTANT.current_states:
            Clock.schedule_once(
                lambda dt: self._build_entity_list(HOME_ASSISTANT.current_states), 0
            )

    # ── Rotary encoder ────────────────────────────────────────────────────────

    def _set_focus(self, idx: int):
        """Move the rotary focus highlight to the card at *idx*."""
        if not self._focusable_cards:
            return
        idx = idx % len(self._focusable_cards)
        if self._focus_idx >= 0:
            self._focusable_cards[self._focus_idx].focused = False
        self._focus_idx = idx
        self._focusable_cards[idx].focused = True

    def _set_focus_card(self, card):
        """Move focus to a specific card instance (called on touch)."""
        try:
            self._set_focus(self._focusable_cards.index(card))
        except ValueError:
            pass

    def on_rotary_turn(self, direction: int, button_pressed: bool):
        """Rotary turn handler.

        - Hold + turn  (button_pressed=True)  → cycle focus among cards.
        - Turn alone   (button_pressed=False) → adjust the focused card's brightness.
        """
        if not self._focusable_cards:
            return False

        if button_pressed:
            # Cycle focus: clockwise = next, counter-clockwise = previous
            self._set_focus(self._focus_idx + direction)
        else:
            # Adjust brightness of focused card (lights only)
            if 0 <= self._focus_idx < len(self._focusable_cards):
                card = self._focusable_cards[self._focus_idx]
                if hasattr(card, 'adjust_brightness'):
                    card.adjust_brightness(direction * 5.0)
        return False

    def on_rotary_pressed(self):
        """Rotary press — toggle the focused card's switch."""
        if 0 <= self._focus_idx < len(self._focusable_cards):
            self._focusable_cards[self._focus_idx].do_toggle()
        return False