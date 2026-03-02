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
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget

from components.Switch.switch import PiHomeSwitch  # noqa — registers kv rules
from components.Keyboard.keyboard import PiTextInput  # noqa — registers kv class
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
            self.config.write()


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
            self.config.write()


# ─────────────────────────────────────────────────────────────────────────────
# Options dropdown popup
# ─────────────────────────────────────────────────────────────────────────────
class OptionsDropdown(ModalView):
    """Full-screen scrim with a centred card listing all choices."""
    title        = StringProperty('')
    options      = ListProperty([])
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([0.5, 0.5, 0.5, 1])
    accent_color = ColorProperty([0.36, 0.67, 1.0, 1.0])
    card_color   = ColorProperty([0.12, 0.12, 0.14, 1])
    on_pick      = ObjectProperty(lambda val: None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = [0, 0, 0, 0.55]
        self.background       = ''
        self.auto_dismiss     = True
        Clock.schedule_once(self._build, 0)

    def _build(self, dt):
        self.clear_widgets()

        row_h  = dp(48)
        hdr_h  = dp(52)
        pad    = dp(16)
        card_w = dp(340)
        card_h = hdr_h + len(self.options) * row_h + pad

        from kivy.graphics import Color as KColor, RoundedRectangle as RR

        card = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            size=(card_w, card_h),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
        )

        with card.canvas.before:
            KColor(rgba=self.card_color)
            self._card_bg = RR(pos=card.pos, size=card.size, radius=[dp(18)])
        card.bind(pos=lambda *_: setattr(self._card_bg, 'pos', card.pos),
                  size=lambda *_: setattr(self._card_bg, 'size', card.size))

        # Header
        hdr = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=hdr_h,
            padding=[dp(20), 0, dp(14), 0],
        )
        hdr_lbl = Label(
            text=self.title,
            font_name='Nunito', font_size='14sp', bold=True,
            color=(self.text_color[0], self.text_color[1], self.text_color[2], 0.6),
            halign='left', valign='middle',
            size_hint_x=1,
        )
        hdr_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        hdr.add_widget(hdr_lbl)

        # Close X
        close_box = BoxLayout(size_hint=(None, None), size=(dp(32), dp(32)),
                              pos_hint={'center_y': 0.5})
        close_lbl = Label(text='✕', font_name='ArialUnicode', font_size='14sp',
                          color=(self.text_color[0], self.text_color[1], self.text_color[2], 0.45))
        close_box.add_widget(close_lbl)
        close_box.bind(on_touch_down=lambda inst, touch:
                       inst.collide_point(*touch.pos) and self.dismiss())
        hdr.add_widget(close_box)
        card.add_widget(hdr)

        # Option rows
        for opt in self.options:
            row = self._make_option_row(opt, row_h, card_w)
            card.add_widget(row)

        # Bottom padding spacer
        card.add_widget(Widget(size_hint_y=None, height=pad))

        self.add_widget(card)

    def _make_option_row(self, opt, row_h, card_w):
        from kivy.graphics import (
            Color as KColor, RoundedRectangle as RR, Rectangle as Rect
        )

        row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=row_h,
            padding=[dp(20), dp(4), dp(16), dp(4)],
            spacing=dp(10),
        )

        # Subtle divider at top
        with row.canvas.before:
            KColor(rgba=(1, 1, 1, 0.05))
            Rect(pos=row.pos, size=(card_w, dp(1)))

        lbl = Label(
            text=opt,
            font_name='Nunito', font_size='15sp',
            color=self.text_color,
            halign='left', valign='middle',
            size_hint_x=1,
        )
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        row.add_widget(lbl)

        check = Label(
            text='✓',
            font_name='ArialUnicode', font_size='16sp',
            color=(self.accent_color[0], self.accent_color[1], self.accent_color[2], 0),
            size_hint=(None, 1), width=dp(24),
        )
        row.add_widget(check)

        # Highlight the row on touch
        def _on_touch(inst, touch):
            if inst.collide_point(*touch.pos):
                self.on_pick(opt)
                self.dismiss()
                return True
        row.bind(on_touch_down=_on_touch)
        row._check = check
        return row

    def set_current(self, current_value):
        """Highlight the currently-selected option after build."""
        if not self.children:
            return
        card = self.children[0]   # BoxLayout card added directly
        for child in card.children:
            check = getattr(child, '_check', None)
            if check is None:
                continue
            lbl = child.children[-1]           # first Label in row
            is_sel = (lbl.text == current_value)
            check.color = (
                self.accent_color[0], self.accent_color[1],
                self.accent_color[2], 1.0 if is_sel else 0
            )
            lbl.bold = is_sel


# ─────────────────────────────────────────────────────────────────────────────
# Options row
# ─────────────────────────────────────────────────────────────────────────────
class SettingsOptionsRow(SettingsRowBase):
    options = ListProperty([])
    value   = StringProperty('')

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config

    def open_dropdown(self):
        # Derive an opaque card colour from the row's background
        c = self.bg_color
        card_c = (c[0] * 0.80, c[1] * 0.80, c[2] * 0.80, 1.0)
        dropdown = OptionsDropdown(
            title=self.title,
            options=self.options,
            text_color=self.text_color,
            muted_color=self.muted_color,
            accent_color=self.accent_color,
            card_color=card_c,
        )
        def _pick(val):
            self.value = val
        dropdown.on_pick = _pick
        dropdown.open()
        Clock.schedule_once(lambda dt: dropdown.set_current(self.value), 0.05)

    def on_value(self, instance, val):
        if self.section and self.key:
            self.config.adddefaultsection(self.section)
            self.config.set(self.section, self.key, val)
            self.config.write()


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

        # Collect all manifests that have settings, then sort by settingsIndex.
        # Manifests without settingsIndex fall back to 9999 and appear after
        # all explicitly-indexed panels.
        _raw_panels = []
        for manifest_path in glob.glob('./screens/*/manifest.json'):
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
            sort_key = manifest.get('settingsIndex', 9999)
            for c in settings_data:
                if 'section' in c and 'key' in c:
                    config.adddefaultsection(c['section'])
                    config.setdefault(c['section'], c['key'], '')
            _raw_panels.append((sort_key, label, settings_data))

        _raw_panels.sort(key=lambda t: t[0])
        for _, label, settings_data in _raw_panels:
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
        """Persist config, close settings, then do a live reload.
        reload_configuration() handles: CONFIG.reload(), wallpaper restart,
        and on_config_update() on every screen (which re-applies theme colors).
        Do NOT call restart() — that calls self.stop() which kills the process on Pi.
        """
        self.config.write()
        self.go_back()
        from util.helpers import get_app
        get_app().reload_configuration()

    def updated(self, section, key, value):
        pass  # writes happen immediately in each row's on_value

    def closed(self, settings):
        pass  # kept for compatibility
