from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.Image.networkimage import NetworkImage
from composites.AppMenu.appicon import AppIcon
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from theme.color import Color
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.uix.scrollview import ScrollView
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from util.helpers import get_app
from util.tools import hex
from kivy.uix.widget import Widget
from kivy.uix.button import Button

Builder.load_file("./composites/AppMenu/appmenu.kv")

class AppMenu(FloatLayout):

    background_color = ColorProperty((0,0,0, 0.8))
    _menu_active = False

    def __init__(self, screens, **kwargs):
        super(AppMenu, self).__init__(**kwargs)
        self.screens = screens
        self.build()
        self.show_apps()
        self.hide()



    def build(self):
        pad_x   = dp(14)
        spacing = dp(16)
        screen_w = Window.width
        # How many columns fit if each icon is at least dp(100) wide?
        cols = max(3, int((screen_w - pad_x * 2 + spacing) / (dp(100) + spacing)))
        icon_w = (screen_w - pad_x * 2 - spacing * (cols - 1)) / cols
        icon_h = round(icon_w * 1.20)
        self.icon_w = icon_w
        self.icon_h = icon_h

        view = ScrollView(size_hint=(1, 1), pos_hint={'center_x': 0.5, 'center_y': 0.5}, do_scroll_x=False, do_scroll_y=True, bar_width=0)
        self.grid = GridLayout(
            cols=cols,
            padding=(pad_x, dp(60), pad_x, dp(20)),
            spacing=spacing,
            size_hint=(1, None),
            col_default_width=icon_w,
            col_force_default=True,
            row_default_height=icon_h,
            row_force_default=True,
        )
        self.grid.bind(minimum_height=self.grid.setter('height'))

        view.add_widget(self.grid)
        self.add_widget(view)
        self.view = view


    def open_app(self, key):
        if not self._menu_active:
            return
        # Start the dismiss animation immediately so the menu is visibly
        # closing, then navigate after a short delay. This ensures slow-loading
        # screens show their loading state rather than appearing frozen behind
        # the still-open menu.
        self.dismiss()
        get_app().menu_button.is_open = False
        get_app().app_menu_open = False
        Clock.schedule_once(lambda _: PIHOME_SCREEN_MANAGER.goto(key), 0.18)


    def hide(self):
        self.opacity = 0
        self._menu_active = False
        offscreen_y = Window.height + 100
        self.pos = (0, offscreen_y)
        self.grid.pos = (0, offscreen_y)
        self.view.pos = (0, offscreen_y)
        # Reset all icons so they're ready for the next open
        for icon in self.grid.children:
            icon.reset_anim()

    def dismiss(self):
        """Animated close — icons slide up and fade, then snap offscreen."""
        self._menu_active = False
        icons = list(self.grid.children)  # reversed insertion order = bottom-right first
        total = len(icons)
        for i, icon in enumerate(icons):
            icon.animate_out(delay=i * 0.04, on_complete=None)
        # Fade the background.  hide() is bound to THIS animation's on_complete so it
        # is always called — even on Pi where icon animation callbacks can be delayed
        # by frame-rate drops or SFX/audio initialisation on the main thread.
        fade = Animation(opacity=0, t='linear', d=0.15 + total * 0.04)
        fade.bind(on_complete=lambda *_: self.hide())
        fade.start(self)

    def show(self):
        self._menu_active = True
        self.pos = (0, 0)
        self.view.pos = (0, 0)
        self.grid.pos = (0, 0)
        # Fade in background instantly
        Animation.cancel_all(self, 'opacity')
        self.opacity = 1
        # Stagger each icon in (grid.children is reversed, so reverse again for top-left first)
        icons = list(reversed(self.grid.children))
        for i, icon in enumerate(icons):
            icon.animate_in(delay=i * 0.06)



    def reset(self):
        self.grid.clear_widgets()

    # ── Touch handling — consume ALL touches when menu is visible ────────────

    def on_touch_down(self, touch):
        if not self._menu_active:
            return False
        # Dispatch to children (AppIcons) then consume regardless
        super().on_touch_down(touch)
        return True

    def on_touch_move(self, touch):
        if not self._menu_active:
            return False
        super().on_touch_move(touch)
        return True

    def on_touch_up(self, touch):
        if not self._menu_active:
            return False
        super().on_touch_up(touch)
        return True

    def show_apps(self):
        count = 0
        for i in self.screens:
            if not self.screens[i].is_hidden:
                icon = self.screens[i].icon
                label = self.screens[i].label
                self.grid.add_widget(AppIcon(icon=icon, label=label, app_key=i, on_select=(lambda key: self.open_app(key)), size=(self.icon_w, self.icon_h)))
                count += 1