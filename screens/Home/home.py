import subprocess
from components.Image.networkimage import NetworkImage
from components.Slider.slidecontrol import SlideControl

from composites.Reddit.redditwidget import RedditWidget
from composites.HomeAssistant.hadevicecard import make_ha_card, load_ha_favorites  # noqa — also loads hadevicecard.kv
from services.homeassistant.homeassistant import HOME_ASSISTANT
import requests
import time
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty, NumericProperty,ListProperty, BooleanProperty

from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.SmartLight.smartlight import SmartLight
from composites.Weather.weatherwidget import WeatherWidget
from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from listeners.ConfigurationUpdateListener import ConfigurationUpdateListener
from services.audio.audioplayernew import AUDIO_PLAYER
from services.audio.sfx import SFX
from services.qr.qr import QR
from services.wallpaper.wallpaper import WALLPAPER_SERVICE
from services.weather.weather import WEATHER
from system.brightness import get_brightness, set_brightness
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import appmenu_open, get_app
from util.tools import hex
from kivy.clock import Clock
from kivy.animation import Animation
from util.const import (
    _SETTINGS_SCREEN, CDN_ASSET,
    GESTURE_SWIPE_DOWN, GESTURE_SWIPE_DOWN_FROM_TOP, GESTURE_SWIPE_UP,
    GESTURE_SWIPE_LEFT_TO_RIGHT, GESTURE_SWIPE_RIGHT_TO_LEFT,
)

Builder.load_file("./screens/Home/home.kv")

class HomeScreen(PiHomeScreen):
    theme = Theme()
    color = ColorProperty()
    time = StringProperty("--:-- -M")
    date = StringProperty("Saturday July 29, 2022")
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY, 0.3))

    logo_opacity = NumericProperty(1)

    date_time_y_offset = NumericProperty(-100)
    date_time_opacity = NumericProperty(0)
    weather_opacity = NumericProperty(0)

    weather_code = StringProperty("--")

    is_first_run = True
    brightness_slider = None
    banButton = None
    qr_img = None
    _qr_poll_event = None
    _qr_last_source = None

    # ── HA favorites panel state ──────────────────────────────────────────────
    _ha_card      = None   # currently displayed HADeviceCard widget, or None
    _ha_favorites = []     # ordered list of favorited entity_ids
    _ha_idx       = -1     # index into _ha_favorites of the displayed card (-1 = none shown)


    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.disable_rotary_press_animation = True

        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY, 0.4)
        self.size = App.get_running_app().get_size()
        Clock.schedule_interval(lambda _: self.run(), 1)
        self.on_gesture = self.handle_gesture


    def on_enter(self, *args):
        if self.is_first_run is True:
            Clock.schedule_once(lambda _: self.startup_animation(), 10)
            self.is_first_run = False

        return super().on_enter(*args)

    def change_brightness(self, value):
        set_brightness(value)

    def open_settings(self):
        PIHOME_SCREEN_MANAGER.goto(_SETTINGS_SCREEN)

    def open_pin(self):
        self.manager.current = 'pin'

    def startup_animation(self):
        SFX.play("startup")
        animation = Animation(logo_opacity = 0, t='linear', d=1)
        animation &= Animation(date_time_opacity = 1, t='out_elastic', d=1)
        animation &= Animation(date_time_y_offset = 0, t='out_elastic', d=1)
        animation &= Animation(weather_opacity = 1, t='linear', d=1)
        animation.start(self)

    def run(self):
        time.ctime()
        self.time = time.strftime("%-I:%M%p")
        self.date = time.strftime("%A %B %d, %Y")

        self.weather_code = str(WEATHER.weather_code)

    # ── Gestures ──────────────────────────────────────────────────────────────

    def handle_gesture(self, gesture):
        if gesture == GESTURE_SWIPE_DOWN_FROM_TOP:
            self._handle_swipe_down()
        elif gesture == GESTURE_SWIPE_UP:
            self._handle_swipe_up()
        elif gesture == GESTURE_SWIPE_LEFT_TO_RIGHT:
            self._ha_step(-1)   # swipe right → previous favorite
        elif gesture == GESTURE_SWIPE_RIGHT_TO_LEFT:
            self._ha_step(+1)   # swipe left  → next favorite

    def _handle_swipe_down(self):
        """Swipe down: show the first HA favorite (or nothing if none)."""
        if self._ha_card is not None:
            return  # card already visible — ignore
        favs = sorted(load_ha_favorites())
        if not favs:
            return
        self._ha_favorites = favs
        self._show_ha_card(0)

    def _handle_swipe_up(self):
        """Swipe up: dismiss the current HA card."""
        if self._ha_card is not None:
            self._dismiss_ha_card_animated()

    def _ha_step(self, delta):
        """Cycle through favorites by *delta* (+1 = next, -1 = previous)."""
        favs = sorted(load_ha_favorites())
        if not favs:
            return
        self._ha_favorites = favs
        if self._ha_card is None:
            # No card visible — slide down from above
            idx = 0 if delta > 0 else len(favs) - 1
            self._show_ha_card(idx)
        else:
            new_idx = (self._ha_idx + delta) % len(favs)
            # Slide current card out in the swipe direction, new card in from the opposite edge
            self._slide_ha_card_out(delta, then=lambda: self._slide_ha_card_in(new_idx, delta))

    # ── HA card animation ─────────────────────────────────────────────────────

    def _show_ha_card(self, idx):
        """Create the HA device card for favorites[idx] and slide it down into view."""
        if not self._ha_favorites or idx < 0 or idx >= len(self._ha_favorites):
            return

        eid = self._ha_favorites[idx]
        state_dict = HOME_ASSISTANT.current_states.get(eid)
        if state_dict is None:
            return

        card = make_ha_card(eid, state_dict)
        if card is None:
            return

        card.size_hint = (None, None)
        card.width  = min(dp(360), self.width - dp(32))
        card.height = dp(150)

        target_x = (self.width  - card.width)  / 2.0
        target_y = self.height * 0.72 - card.height / 2.0

        card.opacity = 0
        card.pos = (target_x, target_y + dp(60))

        self._ha_card = card
        self._ha_idx  = idx
        self.add_widget(card)

        Animation(y=target_y, opacity=1, t='out_quad', d=0.35).start(card)

    def _dismiss_ha_card_animated(self, then=None):
        """Slide the HA card upward and fade it out, then optionally call *then*."""
        card = self._ha_card
        if card is None:
            if then:
                then()
            return

        self._ha_card = None  # detach immediately so rotary reverts
        self._ha_idx  = -1
        card.pos_hint = {}
        card.pos = card.pos  # lock absolute position

        anim = Animation(y=card.y + dp(80), opacity=0, t='out_quad', d=0.35)

        def _on_complete(anim, widget):
            if widget.parent:
                self.remove_widget(widget)
            if then:
                then()

        anim.bind(on_complete=_on_complete)
        anim.start(card)

    def _slide_ha_card_out(self, direction, then=None):
        """Slide the current HA card out horizontally.
        direction=+1 (next): exits to the left.
        direction=-1 (prev): exits to the right.
        """
        card = self._ha_card
        if card is None:
            if then:
                then()
            return

        self._ha_card = None
        self._ha_idx  = -1
        card.pos_hint = {}
        card.pos = card.pos  # lock absolute position

        exit_x = (card.x - card.width - dp(32)
                  if direction > 0
                  else card.x + card.width + dp(32))
        anim = Animation(x=exit_x, opacity=0, t='out_quad', d=0.28)

        def _on_complete(anim, widget):
            if widget.parent:
                self.remove_widget(widget)
            if then:
                then()

        anim.bind(on_complete=_on_complete)
        anim.start(card)

    def _slide_ha_card_in(self, idx, from_direction):
        """Create the HA card for favorites[idx] and slide it in horizontally.
        from_direction=+1 (next): enters from the right.
        from_direction=-1 (prev): enters from the left.
        """
        if not self._ha_favorites or idx < 0 or idx >= len(self._ha_favorites):
            return

        eid = self._ha_favorites[idx]
        state_dict = HOME_ASSISTANT.current_states.get(eid)
        if state_dict is None:
            return

        card = make_ha_card(eid, state_dict)
        if card is None:
            return

        card.size_hint = (None, None)
        card.width  = min(dp(360), self.width - dp(32))
        card.height = dp(150)

        target_x = (self.width - card.width) / 2.0
        target_y  = self.height * 0.72 - card.height / 2.0

        # Start off-screen on the opposite edge to the swipe direction
        start_x = (target_x + card.width + dp(32)
                   if from_direction > 0
                   else target_x - card.width - dp(32))

        card.opacity = 0
        card.pos = (start_x, target_y)

        self._ha_card = card
        self._ha_idx  = idx
        self.add_widget(card)

        Animation(x=target_x, opacity=1, t='out_quad', d=0.28).start(card)

    # ── QR sync ─────────────────────────────────────────────────────────────

    def _update_qr(self):
        source = WALLPAPER_SERVICE.source
        self._qr_last_source = source
        qr_path = QR().from_url(source)

        if self.qr_img is not None:
            self.remove_widget(self.qr_img)

        self.qr_img = NetworkImage(qr_path, size=(dp(256), dp(256)), pos=(dp(10), dp(10)))
        self.qr_img.pos = (dp(get_app().width - 320), dp(100))
        self.add_widget(self.qr_img)

    def _check_qr_source(self):
        if self.qr_img is None:
            return
        if WALLPAPER_SERVICE.source != self._qr_last_source:
            self._update_qr()

    # ── Config / lifecycle ────────────────────────────────────────────────────

    def on_config_update(self, config):
        self.ids.weather_widget.on_config_update(config)
        self.ids.reddit_widget.on_config_update(config)
        super().on_config_update(config)

    # ── Rotary encoder ────────────────────────────────────────────────────────

    def on_rotary_long_pressed(self):
        self.toggle_controls()

    def on_rotary_pressed(self):
        if self._ha_card is not None:
            self._ha_card.do_toggle()
            return
        WALLPAPER_SERVICE.shuffle()

    def on_rotary_turn(self, direction, pressed):
        if self._ha_card is not None:
            self._ha_card.adjust_brightness(direction * 5.0)
            return
        if self.brightness_slider is None:
            # default mode, scroll through wallpapers
            if direction == 1:
                WALLPAPER_SERVICE.next()
            elif direction == -1:
                WALLPAPER_SERVICE.previous()
        else:
            if direction == 1:
                self.brightness_slider.set_value(self.brightness_slider.level + 5)
            elif direction == -1:
                self.brightness_slider.set_value(self.brightness_slider.level - 5)

    # ── Controls panel ────────────────────────────────────────────────────────

    def toggle_controls(self):
        if self.brightness_slider is None and self.banButton is None:
            self.brightness_slider = SlideControl(size=(dp(20), dp(200)), pos=(dp(get_app().width -30), dp(10)))
            self.brightness_slider.add_listener(lambda value: self.change_brightness(value))
            self.brightness_slider.background_color = hex(Color.CHARTREUSE_600, 0.1)
            self.brightness_slider.active_color = hex(Color.DARK_CHARTREUSE_700)
            self.brightness_slider.level = get_brightness()
            self.add_widget(self.brightness_slider)

            self.banButton = SimpleButton(type="danger")
            self.banButton.text = "Ban Wallpaper"
            self.banButton.size = (dp(200), dp(50))
            self.banButton.pos = (dp(get_app().width - 270), dp(10))
            self.banButton.bind(on_release=lambda x: WALLPAPER_SERVICE.ban())
            self.add_widget(self.banButton)

            self._update_qr()
            self._qr_poll_event = Clock.schedule_interval(lambda _: self._check_qr_source(), 2)
        else:
            if self._qr_poll_event:
                self._qr_poll_event.cancel()
                self._qr_poll_event = None
            self._qr_last_source = None

            self.remove_widget(self.brightness_slider)
            self.brightness_slider = None
            self.remove_widget(self.banButton)
            self.banButton = None

            self.remove_widget(self.qr_img)
            self.qr_img = None