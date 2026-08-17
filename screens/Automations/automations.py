"""AutomationsScreen — every trigger -> event rule in PiHome, in one place.

PiHome's automation rules live in per-service stores: BambuLab printer states,
Emporia power thresholds, Bluetooth command bindings, plus AirPlay and Home
Assistant react listeners. They were previously invisible in the app — the only
way to see or delete one was to POST JSON at the server. This screen lists them
all, grouped by source, and lets you:

  * tap a row to test-fire it (so a rule can be verified without waiting for the
    real trigger)
  * toggle it off without deleting it
  * delete it, with a confirmation

Rules are still *created* through the JSON events and the web event builder —
this screen manages what already exists.

Stores register themselves in util.rulestore.RULE_STORES when their service is
imported, so a screen directory that has been removed simply contributes no
section here; nothing in this file imports another screen's service.
"""

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivy.uix.label import Label

from components.Msgbox.msgbox import MSGBOX_BUTTONS, MSGBOX_FACTORY, MSGBOX_TYPES
from components.Switch.switch import PiHomeSwitch
from interface.pihomescreen import PiHomeScreen
from screens.Automations.automationrow import _DEFAULT_GLYPH, AutomationRow
from theme.theme import Theme
from util.configuration import CONFIG
from util.const import SERVER_PORT
from util.helpers import toast
from util.phlog import PIHOME_LOGGER
from util.rulestore import RULE_STORES, format_age

Builder.load_file("./screens/Automations/automations.kv")


class AutomationsScreen(PiHomeScreen):

    # Defaults derived from the active theme so the first paint is correct —
    # reload_all() never runs at startup (only on a settings/theme change), so a
    # literal default would persist until the user changed something.
    # on_config_update() keeps them in sync afterwards.
    _th = Theme()
    bg_color      = ColorProperty(_th.get_color(_th.BACKGROUND_PRIMARY))
    header_color  = ColorProperty(_th.get_color(_th.BACKGROUND_SECONDARY))
    card_color    = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    row_bg_color  = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    divider_color = ColorProperty(_th.get_color(_th.BACKGROUND_BORDER))
    text_color    = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color   = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    accent_color  = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))
    status_color  = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    danger_color  = ColorProperty(_th.get_color(_th.BUTTON_DANGER))

    is_empty = BooleanProperty(True)
    # Empty-state copy, built from the registered stores so it names the real
    # event types rather than telling the user to send "an automation event".
    empty_hint = StringProperty("")
    empty_events = StringProperty("")

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_enter(self, *args):
        super().on_enter(*args)
        # Pick up services that started after boot (and legacy AirPlay/HA, which
        # only register through their adapters).
        try:
            from util.rule_adapters import register_adapters
            register_adapters()
        except Exception as e:
            PIHOME_LOGGER.error(f"Automations: adapter registration failed: {e}")
        # Apply the theme BEFORE building rows — they capture colors at
        # construction, so a stale palette here would stick until the next visit.
        super().on_config_update(CONFIG)
        self._render()

    def on_config_update(self, config):
        super().on_config_update(config)
        # Rows receive colors at construction, so rebuild them on a theme change.
        if self.is_open:
            self._render()

    # ── Rendering ──────────────────────────────────────────────────────────────

    def _render(self):
        box = self.ids.get("rows_box")
        if box is None:
            return
        box.clear_widgets()

        total = 0
        for key, store in RULE_STORES.items():
            try:
                rules = store.list()["body"].get("rules", [])
            except Exception as e:
                PIHOME_LOGGER.error(f"Automations: store '{key}' failed to list: {e}")
                continue
            if not rules:
                continue
            total += len(rules)
            box.add_widget(self._section_label(store.label, len(rules)))
            for rule in rules:
                box.add_widget(self._make_row(store, rule))

        self.is_empty = total == 0
        if self.is_empty:
            self._build_empty_hint()

    def _build_empty_hint(self):
        """Name the events that actually create automations on THIS install.

        Telling someone to "send an automation event" is useless if they have no
        way to learn what one is called, so list the registered stores' own
        create events. SERVER_PORT is the web app that can build them for you.
        """
        events = []
        for store in RULE_STORES.values():
            name = getattr(store, "create_event", None)
            if name and name not in events:      # two stores may share one
                events.append(name)
        if not events:
            self.empty_hint = "No automation-capable screens are enabled."
            self.empty_events = ""
            return
        self.empty_hint = (
            "Create one by sending any of these events\n"
            f"(web app on port {SERVER_PORT}, Home Assistant, MQTT or HTTP):")
        self.empty_events = "\n".join(
            "  ".join(events[i:i + 2]) for i in range(0, len(events), 2))

    def _section_label(self, label, count):
        lbl = Label(
            text=f"{label.upper()}  ({count})",
            font_name="Nunito",
            font_size="11sp",
            bold=True,
            color=self.muted_color,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(26),
            padding=(dp(12), 0),
        )
        lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        return lbl

    def _make_row(self, store, rule):
        rid = rule.get("id")
        can_toggle = getattr(store, "supports_enable", True)

        row = AutomationRow(
            rule_id=str(rid or ""),
            trigger=store.describe(rule),
            action=store.describe_action(rule),
            last_fired=format_age(rule.get("last_fired")),
            glyph=getattr(store, "glyph", "") or _DEFAULT_GLYPH,
            enabled=bool(rule.get("enabled", True)),
            can_toggle=can_toggle,
            text_color=list(self.text_color),
            muted_color=list(self.muted_color),
            row_bg_color=list(self.row_bg_color),
            danger_color=list(self.danger_color),
            glyph_color=list(self.accent_color),
        )

        # Assigned AFTER construction — an on_* constructor kwarg would be bound
        # as an event instead of set as the callback (CLAUDE.md gotcha #11).
        row.select_cb = lambda s=store, r=dict(rule): self._test_fire(s, r)
        row.delete_cb = lambda s=store, i=rid, r=dict(rule): self._confirm_delete(s, i, r)

        if can_toggle:
            switch = PiHomeSwitch(size=(dp(46), dp(26)))
            # Snap to the stored state without animating and without firing the
            # handler — otherwise every rebuild would slide all the switches and
            # re-enter _toggle (which re-renders, which rebuilds...).
            switch.set_state(rule.get("enabled", True), animate=False)
            switch.on_change = lambda value, s=store, i=rid: self._toggle(s, i, value)
            row.attach_switch(switch)

        return row

    # ── Actions ────────────────────────────────────────────────────────────────

    def _test_fire(self, store, rule):
        """Fire the rule's action now, regardless of enabled state or cooldown."""
        try:
            fired = store.fire(rule, force=True)
        except Exception as e:
            PIHOME_LOGGER.error(f"Automations: test-fire failed: {e}")
            toast("Could not fire that automation", "error", 3)
            return
        if not fired:
            toast("That automation has no action to fire", "warning", 3)
            return
        toast(f"Fired: {store.describe_action(rule)}", "success", 3)
        # last_fired changed — refresh so the row's timestamp is honest.
        Clock.schedule_once(lambda dt: self._render(), 0.2)

    def _toggle(self, store, rid, value):
        response = store.set_enabled(rid, value)
        if response["code"] != 200:
            toast(response["body"].get("message", "Could not update"), "error", 3)
        Clock.schedule_once(lambda dt: self._render(), 0)

    def _confirm_delete(self, store, rid, rule):
        MSGBOX_FACTORY.show(
            title="Delete Automation",
            message=f"Delete this automation?\n\n{store.describe(rule)}",
            type=MSGBOX_TYPES["WARNING"],
            buttons=MSGBOX_BUTTONS["YES_NO"],
            on_yes=lambda s=store, i=rid: self._delete(s, i),
        )

    def _delete(self, store, rid):
        response = store.remove(rid)
        if response["code"] != 200:
            toast(response["body"].get("message", "Could not delete"), "error", 3)
        else:
            toast("Automation deleted", "success", 2)
        self._render()

    # ── Rotary encoder ─────────────────────────────────────────────────────────

    def on_rotary_pressed(self):
        """Refresh the list."""
        self._render()
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True
