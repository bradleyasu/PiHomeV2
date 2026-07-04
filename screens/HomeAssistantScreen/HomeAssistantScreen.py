from threading import Thread

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from composites.HomeAssistant.hadevicecard import (  # noqa — registers kv rules
    HACoverCard, HALightCard, HATriggerCard, HAToggleCard,
    HAClimateCard, HAMediaCard,
    make_ha_card, load_ha_favorites, SUPPORTED_DOMAINS,
)
from interface.pihomescreen import PiHomeScreen
from services.homeassistant.homeassistant import HOME_ASSISTANT, HomeAssistantListener
from theme import theme as t

Builder.load_file("./screens/HomeAssistantScreen/HomeAssistantScreen.kv")

# ─────────────────────────────────────────────────────────────────────────────
# HaListenerRow
# ─────────────────────────────────────────────────────────────────────────────

class HaListenerRow(BoxLayout):
    """Single row in the Listeners tab."""

    listener_id   = StringProperty("")
    entity_label  = StringProperty("")   # entity_id text
    trigger_label = StringProperty("")   # e.g. "On state 'on'" or "On any change"
    action_label  = StringProperty("")   # e.g. "→ execute alert"
    text_color    = ColorProperty([1, 1, 1, 0.9])
    muted_color   = ColorProperty([1, 1, 1, 0.4])
    accent_color  = ColorProperty([0.737, 0.384, 0.251, 1.0])
    on_delete_cb  = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        cb = kwargs.pop('on_delete_cb', None)
        super().__init__(**kwargs)
        if cb is not None:
            self.on_delete_cb = cb
        Clock.schedule_once(self._build_canvas)

    def _build_canvas(self, *_):
        strip = self.ids.accent_strip
        with strip.canvas:
            self._strip_color = Color(*self.accent_color)
            self._strip_rect  = Rectangle(pos=strip.pos, size=strip.size)
        strip.bind(pos=self._update_strip, size=self._update_strip)
        self.bind(accent_color=lambda *a: setattr(self._strip_color, 'rgba', self.accent_color))

        with self.canvas.after:
            tc = self.text_color
            self._sep_color = Color(tc[0], tc[1], tc[2], 0.06)
            self._sep_rect  = Rectangle(pos=(self.x, self.y), size=(self.width, dp(1)))
        self.bind(pos=self._update_sep, size=self._update_sep)

    def _update_strip(self, *_):
        s = self.ids.accent_strip
        self._strip_rect.pos  = s.pos
        self._strip_rect.size = s.size

    def _update_sep(self, *_):
        self._sep_rect.pos  = (self.x, self.y)
        self._sep_rect.size = (self.width, dp(1))

    def on_touch_down(self, touch):
        if self.ids.delete_lbl.collide_point(*touch.pos):
            if self.on_delete_cb:
                self.on_delete_cb(self.listener_id)
            return True
        return super().on_touch_down(touch)

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

# Favorites row height must fit a light card (switch row + brightness slider).
_FAV_ROW_H = dp(108)
# Cards created per Clock frame while (re)building the list. Small enough that
# the first frame stays cheap (so the app-menu slide-out never hitches), large
# enough that a full dashboard finishes streaming in well under a second.
_BUILD_CHUNK = 5


def _domain_of(entity_id: str) -> str:
    return entity_id.split(".", 1)[0] if "." in entity_id else ""


class HomeAssistantScreen(PiHomeScreen):

    bg_color     = ColorProperty([0, 0, 0, 1])
    header_color = ColorProperty([0, 0, 0, 1])
    text_color   = ColorProperty([1, 1, 1, 1])
    accent_color = ColorProperty([0.737, 0.384, 0.251, 1.0])
    view_mode    = StringProperty('devices')   # 'devices' | 'listeners'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Theme colours
        theme = t.Theme()
        self.bg_color     = theme.get_color(t.Theme.BACKGROUND_PRIMARY)
        self.header_color = theme.get_color(t.Theme.BACKGROUND_SECONDARY)
        self.text_color   = theme.get_color(t.Theme.TEXT_PRIMARY)
        self.accent_color = theme.get_color(t.Theme.ACCENT_PRIMARY)

        self._card_registry: dict = {}
        self._focusable_cards: list = []   # ordered flat list for rotary navigation
        self._focus_idx: int = -1
        self._built_signature = None       # detects when a rebuild is actually needed
        self._build_queue: list = []       # pending incremental-build work items
        self._build_token = 0              # bumped to cancel a superseded build

        # Register HA state listener
        self._listener = HomeAssistantListener(self._on_state_change)
        HOME_ASSISTANT.add_listener(self._listener)

    # ── Screen lifecycle ──────────────────────────────────────────────────────

    def on_pre_enter(self, *args):
        # Always return to the devices tab on each entry
        if self.view_mode != 'devices':
            self.view_mode = 'devices'
        # Build straight from the cached states — no artificial delay. The build
        # streams cards in a few per frame, so the menu animation stays smooth,
        # and if nothing changed since last visit it's a near-instant no-op.
        if HOME_ASSISTANT.current_states:
            self._build_entity_list(HOME_ASSISTANT.current_states)
        else:
            self._show_loading()
            self.refresh()
        return super().on_pre_enter(*args)

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self):
        """Fetch all HA states in a background thread, then rebuild the UI."""
        def _fetch():
            states = HOME_ASSISTANT.get_all_states()
            Clock.schedule_once(lambda dt: self._on_fetch_result(states), 0)

        Thread(target=_fetch, daemon=True).start()

    def _on_fetch_result(self, states):
        """Main-thread handler for a background state fetch."""
        if states is None:
            # Network-level failure — HA configured but unreachable.
            self._show_message(
                '',  # cloud_off
                'Home Assistant unreachable',
                'Check the connection, then tap refresh to retry.',
            )
        elif not HOME_ASSISTANT.ha_is_available:
            self._show_message(
                '',  # settings
                'Home Assistant not configured',
                'Add your HA host and token in Settings.',
            )
        else:
            HOME_ASSISTANT.current_states = states
            self._build_entity_list(states)

    def on_tab_devices(self):
        """Switch to the Devices tab."""
        if self.view_mode == 'devices':
            return
        self.view_mode = 'devices'
        if HOME_ASSISTANT.current_states:
            self._build_entity_list(HOME_ASSISTANT.current_states)
        else:
            self._show_loading()
            self.refresh()

    def on_tab_listeners(self):
        """Switch to the Listeners tab."""
        if self.view_mode == 'listeners':
            return
        self.view_mode = 'listeners'
        # Cancel any in-flight device build and force a rebuild next time we
        # return to Devices (its card widgets are about to be cleared).
        self._build_token += 1
        self._built_signature = None
        Clock.schedule_once(lambda dt: self._build_listeners_list(), 0)

    def on_config_update(self, config):
        """Reconnect Home Assistant service if URL or token changed."""
        old_url   = getattr(HOME_ASSISTANT, 'HA_URL',   '')
        old_token = getattr(HOME_ASSISTANT, 'HA_TOKEN', '')

        HOME_ASSISTANT.configure_connection()

        if HOME_ASSISTANT.HA_URL != old_url or HOME_ASSISTANT.HA_TOKEN != old_token:
            HOME_ASSISTANT.is_shutting_down = False
            HOME_ASSISTANT.shutdown()
            HOME_ASSISTANT.is_shutting_down = False
            HOME_ASSISTANT.connect()

        super().on_config_update(config)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _show_loading(self):
        """Centred hourglass + 'Loading...' placeholder."""
        self._show_message('\ue863', 'Loading...', '')   # hourglass_empty

    def _show_message(self, icon_glyph, title, subtitle=''):
        """Fill scroll_content with a vertically-centred icon + title (+ subtitle).

        Single entry point for every non-list state: loading, no devices,
        unreachable, unconfigured. Cancels any in-flight build so streamed
        cards can't land on top of the message.
        """
        self._build_token += 1
        self._built_signature = None
        scroll_content = self.ids.get('scroll_content')
        if scroll_content is None:
            return
        scroll_content.clear_widgets()
        self._card_registry.clear()
        self._focusable_cards = []
        self._focus_idx = -1

        tc = self.text_color
        # Top spacer pushes the block toward the vertical centre of the ~392dp
        # content area on a 480px display.
        scroll_content.add_widget(Widget(size_hint_y=None, height=dp(120)))

        icon_lbl = Label(
            text=icon_glyph,
            font_name='MaterialIcons',
            font_size='42sp',
            color=(tc[0], tc[1], tc[2], 0.22),
            size_hint_y=None, height=dp(56),
            halign='center', valign='middle',
        )
        icon_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        scroll_content.add_widget(icon_lbl)

        title_lbl = Label(
            text=title,
            font_name='Nunito', font_size='15sp',
            color=(tc[0], tc[1], tc[2], 0.4),
            size_hint_y=None, height=dp(30),
            halign='center', valign='middle',
        )
        title_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        scroll_content.add_widget(title_lbl)

        if subtitle:
            sub_lbl = Label(
                text=subtitle,
                font_name='Nunito', font_size='11sp',
                color=(tc[0], tc[1], tc[2], 0.28),
                size_hint_y=None, height=dp(22),
                halign='center', valign='middle',
            )
            sub_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            scroll_content.add_widget(sub_lbl)

    # ── Listeners tab ─────────────────────────────────────────────────────────

    def _build_listeners_list(self):
        """Populate scroll_content with listener rows (or an empty state)."""
        scroll_content = self.ids.get('scroll_content')
        if scroll_content is None:
            return
        scroll_content.clear_widgets()

        listeners = HOME_ASSISTANT.ha_react_listeners

        if not listeners:
            # ── Empty state — vertically centred ────────────────────────────
            # Top spacer pushes content to visual centre
            scroll_content.add_widget(Widget(size_hint_y=None, height=dp(80)))

            icon_lbl = Label(
                text='\ue7f7',          # \ue7f7 = notifications_none  (Material Icons)
                font_name='MaterialIcons',
                font_size='42sp',
                color=(self.text_color[0], self.text_color[1], self.text_color[2], 0.2),
                size_hint_y=None,
                height=dp(52),
                halign='center',
                valign='middle',
            )
            icon_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            scroll_content.add_widget(icon_lbl)

            empty_lbl = Label(
                text='No listeners configured',
                font_name='Nunito',
                font_size='15sp',
                color=(self.text_color[0], self.text_color[1], self.text_color[2], 0.35),
                size_hint_y=None,
                height=dp(28),
                halign='center',
                valign='middle',
            )
            empty_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            scroll_content.add_widget(empty_lbl)

            sub_lbl = Label(
                text='Use the hareact webhook event to add one.',
                font_name='Nunito',
                font_size='11sp',
                color=(self.text_color[0], self.text_color[1], self.text_color[2], 0.2),
                size_hint_y=None,
                height=dp(20),
                halign='center',
                valign='middle',
            )
            sub_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            scroll_content.add_widget(sub_lbl)
            return

        scroll_content.add_widget(
            self._section_label(f"LISTENERS  ({len(listeners)})")
        )
        for listener in listeners:
            scroll_content.add_widget(self._make_listener_row(listener))

    def _make_listener_row(self, listener):
        state_part   = f"state = '{listener.state}'" if listener.state else "any change"
        trigger_lbl  = f"When {state_part}"
        action_type  = listener.action.get('type', 'event') if isinstance(listener.action, dict) else 'event'
        action_lbl   = f"execute {action_type}"

        row = HaListenerRow(
            listener_id   = listener.id,
            entity_label  = listener.entity_id,
            trigger_label = trigger_lbl,
            action_label  = action_lbl,
            text_color    = list(self.text_color),
            muted_color   = [self.text_color[0], self.text_color[1], self.text_color[2], 0.4],
            accent_color  = list(self.accent_color),
        )
        row.on_delete_cb = self._delete_listener
        return row

    def _delete_listener(self, listener_id: str):
        HOME_ASSISTANT.remove_react_listener(listener_id)
        # Rebuild the listeners list to reflect the removal
        Clock.schedule_once(lambda _: self._build_listeners_list(), 0)

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

    # ── Section layout ──────────────────────────────────────────────────────────

    def _compute_sections(self, states: dict):
        """Return [(title, [(entity_id, state_dict), ...], row_height), ...].

        Favorites first (any supported domain), then the domain GROUPS with the
        already-placed favorites removed. Purely a function of the data, so two
        calls with the same devices/favorites produce an identical structure —
        which _signature() uses to decide whether a rebuild is even needed.
        """
        favs = load_ha_favorites()
        fav_ids = [
            eid for eid in sorted(favs)
            if eid in states and _domain_of(eid) in SUPPORTED_DOMAINS
        ]
        placed = set(fav_ids)

        sections = []
        if fav_ids:
            sections.append(("FAVORITES",
                             [(eid, states[eid]) for eid in fav_ids],
                             _FAV_ROW_H))

        for section_title, domains, _card_cls, row_h in GROUPS:
            entities = [
                (eid, sdict)
                for eid, sdict in states.items()
                if any(eid.startswith(d + '.') for d in domains)
                and eid not in placed
            ]
            if entities:
                placed.update(eid for eid, _ in entities)
                sections.append((section_title, entities, row_h))
        return sections

    @staticmethod
    def _signature(sections):
        """Hashable fingerprint of section titles + entity_ids (order-sensitive).

        Ignores state values, so on/off/brightness changes (handled live by
        _on_state_change) don't trigger a rebuild; only add/remove/favorite
        changes do.
        """
        return tuple(
            (title, tuple(eid for eid, _ in entities))
            for title, entities, _row_h in sections
        )

    def _make_card(self, entity_id, state_dict, favorites):
        card = make_ha_card(entity_id, state_dict, favorites=favorites)
        if card is None:
            return None
        card.size_hint = (1, 1)
        card.bind(is_favorite=self._on_favorite_changed)
        card._focus_callback = self._set_focus_card
        self._card_registry[entity_id] = card
        return card

    def _build_entity_list(self, states: dict, preserve_scroll: bool = False):
        """(Re)build the device dashboard, streaming cards a few per frame.

        Rebuilds only when the set/placement of entities actually changed;
        otherwise it just pushes fresh state into the existing cards (instant,
        no flicker, scroll position kept). The heavy work — card widget
        construction — is spread across frames so the UI never freezes.
        """
        scroll_content = self.ids.get('scroll_content')
        if scroll_content is None:
            return

        sections = self._compute_sections(states)
        if not sections:
            self._show_message('\ue90f',   # lightbulb_outline
                               'No devices found',
                               'No supported Home Assistant entities to show.')
            return

        signature = self._signature(sections)
        if signature == self._built_signature and self._card_registry:
            # Same devices as last build — just refresh their state in place.
            self._sync_existing(states)
            return

        # A real rebuild. Cancel any in-flight one and start fresh.
        self._build_token += 1
        token = self._build_token
        self._built_signature = signature
        scroll_content.clear_widgets()
        self._card_registry.clear()
        self._focusable_cards = []
        self._focus_idx = -1

        scroll_y = self.ids.scroll_view.scroll_y if preserve_scroll and 'scroll_view' in self.ids else None
        favorites = load_ha_favorites()

        # Section headers + empty grids are cheap; add them now so the list has
        # its full height immediately. Card construction is queued.
        queue = []
        for title, entities, row_h in sections:
            scroll_content.add_widget(self._section_label(title))
            grid = self._make_grid(row_h)
            scroll_content.add_widget(grid)
            scroll_content.add_widget(Widget(size_hint_y=None, height=dp(8)))
            for eid, sdict in entities:
                queue.append((grid, eid, sdict))
            # Trailing marker: pad the odd column of this grid once its cards land.
            queue.append(('pad', grid, len(entities)))

        self._build_queue = queue
        self._drain_build_queue(token, favorites, scroll_y)

    def _drain_build_queue(self, token, favorites, scroll_y):
        """Process a chunk of the build queue per frame until drained."""
        if token != self._build_token:
            return  # superseded by a newer build / message
        for _ in range(_BUILD_CHUNK):
            if not self._build_queue:
                # Done: build the flat focus list and select the first card.
                self._focusable_cards = list(self._card_registry.values())
                self._focus_idx = -1
                if self._focusable_cards:
                    self._set_focus(0)
                if scroll_y is not None and 'scroll_view' in self.ids:
                    self.ids.scroll_view.scroll_y = scroll_y
                return
            item = self._build_queue.pop(0)
            if item[0] == 'pad':
                _, grid, count = item
                if count % 2 == 1:
                    grid.add_widget(Widget())
                continue
            grid, eid, sdict = item
            card = self._make_card(eid, sdict, favorites)
            if card is not None:
                grid.add_widget(card)
        Clock.schedule_once(
            lambda dt: self._drain_build_queue(token, favorites, scroll_y), 0
        )

    def _sync_existing(self, states: dict):
        """Push fresh state into already-built cards without rebuilding."""
        for eid, card in self._card_registry.items():
            sdict = states.get(eid)
            if not isinstance(sdict, dict):
                continue
            card.update_state(sdict.get("state", "off"), sdict.get("attributes", {}))

    def _on_state_change(self, entity_id: str, state_str: str, state_dict: dict):
        """Called by HA WebSocket listener (possibly on a background thread)."""
        card = self._card_registry.get(entity_id)
        if card is not None:
            attributes = state_dict.get("attributes", {}) if isinstance(state_dict, dict) else {}
            Clock.schedule_once(lambda dt: card.update_state(state_str, attributes), 0)

    def _on_favorite_changed(self, card, value):
        """Re-place a starred/un-starred card. Rebuilds (incrementally, keeping
        scroll position) since the card moves between the Favorites section and
        its domain group."""
        if HOME_ASSISTANT.current_states:
            Clock.schedule_once(
                lambda dt: self._build_entity_list(
                    HOME_ASSISTANT.current_states, preserve_scroll=True), 0
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