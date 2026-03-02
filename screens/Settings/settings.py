import json
import glob
import os

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.config import ConfigParser
from kivy.properties import (
    BooleanProperty, ColorProperty, ListProperty,
    ObjectProperty, StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget

from components.Switch.switch import PiHomeSwitch  # noqa — registers kv rules
from interface.pihomescreen import PiHomeScreen
from theme import theme as t
from util.const import CONF_FILE

Builder.load_file("./screens/Settings/settings.kv")


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar category pill
# ─────────────────────────────────────────────────────────────────────────────
class SettingsSidebarItem(BoxLayout):
    label        = StringProperty('')
    is_selected  = BooleanProperty(False)
    tap_callback = ObjectProperty(lambda: None)
    text_color   = ColorProperty([1, 1, 1, 1])
    accent_color = ColorProperty([0.36, 0.67, 1.0, 1.0])

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.tap_callback()
            return True
        return super().on_touch_down(touch)


# ─────────────────────────────────────────────────────────────────────────────
# Section title separator
# ─────────────────────────────────────────────────────────────────────────────
class SettingsTitleRow(BoxLayout):
    title      = StringProperty('')
    text_color = ColorProperty([1, 1, 1, 1])
    line_color = ColorProperty([0.36, 0.67, 1.0, 1.0])


# ─────────────────────────────────────────────────────────────────────────────
# Base row — shared properties for all key/value rows
# ─────────────────────────────────────────────────────────────────────────────
class SettingsRowBase(BoxLayout):
    title        = StringProperty('')
    desc         = StringProperty('')
    section      = StringProperty('')
    key          = StringProperty('')
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([0.5, 0.5, 0.5, 1])
    accent_color = ColorProperty([0.36, 0.67, 1.0, 1.0])
    bg_color     = ColorProperty([0, 0, 0, 0])


# ─────────────────────────────────────────────────────────────────────────────
# String / Numeric rows
# ─────────────────────────────────────────────────────────────────────────────
class SettingsStringRow(SettingsRowBase):
    value = StringProperty('')

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config

    def on_value(self, instance, val):
        if self.section and self.key:
            self.config.adddefaultsection(self.section)
            self.config.set(self.section, self.key, val)


class SettingsNumericRow(SettingsStringRow):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Bool toggle row
# ─────────────────────────────────────────────────────────────────────────────
class SettingsBoolRow(SettingsRowBase):
    value = BooleanProperty(False)

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config

    def toggle(self):
        self.value = not self.value

    def on_value(self, instance, val):
        if self.section and self.key:
            self.config.adddefaultsection(self.section)
            self.config.set(self.section, self.key, '1' if val else '0')


# ─────────────────────────────────────────────────────────────────────────────
# Options (cycle) row
# ─────────────────────────────────────────────────────────────────────────────
class SettingsOptionsRow(SettingsRowBase):
    options = ListProperty([])
    value   = StringProperty('')

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config

    def cycle_next(self):
        if not self.options:
            return
        idx = self.options.index(self.value) if self.value in self.options else -1
        self.value = self.options[(idx + 1) % len(self.options)]

    def on_value(self, instance, val):
        if self.section and self.key:
            self.config.adddefaultsection(self.section)
            self.config.set(self.section, self.key, val)


# ─────────────────────────────────────────────────────────────────────────────
# Main Settings Screen
# ─────────────────────────────────────────────────────────────────────────────
class SettingsScreen(PiHomeScreen):

    bg_color      = ColorProperty([0, 0, 0, 1])
    header_color  = ColorProperty([0, 0, 0, 1])
    sidebar_color = ColorProperty([0, 0, 0, 0.5])
    divider_color = ColorProperty([0.2, 0.2, 0.2, 1])
    text_color    = ColorProperty([1, 1, 1, 1])
    muted_color   = ColorProperty([0.5, 0.5, 0.5, 1])
    accent_color  = ColorProperty([0.36, 0.67, 1.0, 1.0])
    row_bg_color  = ColorProperty([0, 0, 0, 0.35])

    def __init__(self, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback

        theme = t.Theme()
        self.bg_color     = theme.get_color(t.Theme.BACKGROUND_PRIMARY)
        self.header_color = theme.get_color(t.Theme.BACKGROUND_SECONDARY)
        self.text_color   = theme.get_color(t.Theme.TEXT_PRIMARY)
        self.muted_color  = theme.get_color(t.Theme.TEXT_SECONDARY)
        self.accent_color = theme.get_color(t.Theme.ALERT_INFO)
        hc = self.header_color
        self.sidebar_color = (hc[0] * 0.80, hc[1] * 0.80, hc[2] * 0.80, 1.0)
        self.divider_color = (hc[0] * 0.60, hc[1] * 0.60, hc[2] * 0.60, 1.0)
        self.row_bg_color  = (hc[0], hc[1], hc[2], 0.7)

        config = ConfigParser()
        config.read(CONF_FILE)
        self.config = config

        self._panels = []         # [(label, settings_data)]
        self._sidebar_items = []

        for manifest_path in sorted(glob.glob('./screens/*/manifest.json')):
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            if manifest.get('hidden', False):
                continue
            if 'settings' not in manifest:
                continue
            settings_data = manifest['settings']
            label = manifest.get(
                'settingsLabel',
                manifest.get('label', os.path.basename(os.path.dirname(manifest_path)))
            )
            for c in settings_data:
                if 'section' in c and 'key' in c:
                    config.adddefaultsection(c['section'])
                    config.setdefault(c['section'], c['key'], '')
            self._panels.append((label, settings_data))

        Clock.schedule_once(self._build_ui, 0)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, dt):
        self._build_sidebar()
        if self._panels:
            self._select_panel(0)

    def _build_sidebar(self):
        sidebar = self.ids.settings_sidebar
        sidebar.clear_widgets()
        self._sidebar_items = []

        for i, (label, _) in enumerate(self._panels):
            idx = i
            item = SettingsSidebarItem(
                label=label,
                text_color=self.text_color,
                accent_color=self.accent_color,
                tap_callback=lambda i=idx: self._select_panel(i),
            )
            sidebar.add_widget(item)
            self._sidebar_items.append(item)

        sidebar.add_widget(Widget())   # pushes items to top

    def _select_panel(self, index):
        for i, item in enumerate(self._sidebar_items):
            item.is_selected = (i == index)
        _, settings_data = self._panels[index]
        self._show_panel(settings_data)

    def _show_panel(self, settings_data):
        content = self.ids.settings_content
        content.clear_widgets()
        for item in settings_data:
            row = self._make_row(item)
            if row:
                content.add_widget(row)
        content.add_widget(Widget(size_hint_y=None, height=dp(24)))

    def _make_row(self, item):
        kind    = item.get('type', '')
        section = item.get('section', '')
        key     = item.get('key', '')

        common = dict(
            text_color=self.text_color,
            muted_color=self.muted_color,
            accent_color=self.accent_color,
            bg_color=self.row_bg_color,
            section=section,
            key=key,
            title=item.get('title', ''),
            desc=item.get('desc', ''),
        )

        if kind == 'title':
            return SettingsTitleRow(
                title=item.get('title', ''),
                text_color=self.text_color,
                line_color=self.accent_color,
            )

        raw = ''
        if section and key and self.config.has_option(section, key):
            raw = self.config.get(section, key)

        if kind == 'string':
            return SettingsStringRow(config=self.config, value=raw, **common)

        if kind == 'numeric':
            return SettingsNumericRow(config=self.config, value=raw, **common)

        if kind == 'bool':
            val = raw in ('1', 'true', 'True', 'yes')
            return SettingsBoolRow(config=self.config, value=val, **common)

        if kind == 'options':
            options = item.get('options', [])
            val = raw if raw in options else (options[0] if options else '')
            return SettingsOptionsRow(
                config=self.config, value=val, options=options, **common
            )

        return None

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_and_close(self):
        self.go_back()
        self.config.write()
        from util.helpers import get_app
        get_app().reload_configuration()

    def updated(self, section, key, value):
        self.config.write()
        if self.callback is not None:
            self.callback()

    def closed(self, settings):
        self.config.write()
        if self.callback is not None:
            self.callback()
