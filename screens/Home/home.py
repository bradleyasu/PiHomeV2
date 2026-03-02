import subprocess
from components.Image.networkimage import NetworkImage
from components.Slider.slidecontrol import SlideControl

from composites.Reddit.redditwidget import RedditWidget
from composites.HomeAssistant.hadevicecard import HAMediaCard  # noqa — also loads hadevicecard.kv
from services.homeassistant.homeassistant import HOME_ASSISTANT, HomeAssistantListener
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
from util.const import _SETTINGS_SCREEN, CDN_ASSET, GESTURE_SWIPE_DOWN, GESTURE_SWIPE_UP

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
    _media_card = None
    _splash_done = False
    _media_card_dismissed = False  # True when user has swiped the card away
    _last_touch_start = None         # (x, y) of the most recent touch_down



    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.disable_rotary_press_animation = True

        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY, 0.4)
        self.size = App.get_running_app().get_size()
        # self.icon = CDN_ASSET.format("default_home_icon.png")
        # Clock.schedule_once(lambda _: self.startup_animation(), 10)
        Clock.schedule_interval(lambda _: self.run(), 1)
        self.on_gesture = self.handle_gesture

        # Listen for HA media player state changes
        self._ha_media_listener = HomeAssistantListener(self._on_ha_state_change)
        HOME_ASSISTANT.add_listener(self._ha_media_listener)
        # No initial check here — we wait until after the splash animation


    def on_enter(self, *args):
        if self.is_first_run is True:
            Clock.schedule_once(lambda _: self.startup_animation(), 10)
            self.is_first_run = False
            #SFX.play("notify")

        return super().on_enter(*args)

    def change_brightness(self, value):
        set_brightness(value)

    def open_settings(self):
        # self.manager.current = 'settings'
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
        # After the animation completes (~1.5s), allow media card to appear
        Clock.schedule_once(lambda dt: self._after_splash(), 2)
        # AUDIO_PLAYER.stop()
        # AUDIO_PLAYER.clear_playlist()

    def _after_splash(self):
        self._splash_done = True
        self._check_active_media()

    def run(self):
        time.ctime()
        self.time = time.strftime("%-I:%M%p")
        self.date = time.strftime("%A %B %d, %Y")

        self.weather_code = str(WEATHER.weather_code)

    def handle_gesture(self, gesture):
        if gesture == GESTURE_SWIPE_UP:
            # If the swipe started over the media card, dismiss it for 15 minutes
            if (self._media_card is not None
                    and self._last_touch_start is not None
                    and self._media_card.collide_point(*self._last_touch_start)):
                self._media_card_dismissed = True
                self._dismiss_media_card_animated()
                return
        if gesture == GESTURE_SWIPE_DOWN:
            # Re-show if the card was manually dismissed and a player is still active
            if self._media_card is None and self._media_card_dismissed:
                active = self._find_active_player()
                if active:
                    self._media_card_dismissed = False
                    eid, state_dict = active
                    self._show_media_card_animated(eid, state_dict)

    def on_touch_down(self, touch):
        self._last_touch_start = (touch.x, touch.y)
        return super().on_touch_down(touch)

    def _dismiss_media_card_animated(self):
        """Slide the media card upward and fade it out, then remove it."""
        card = self._media_card
        if card is None:
            return
        self._media_card = None  # detach immediately so rotary reverts
        # Switch from pos_hint to absolute pos so Animation can move it
        card.pos_hint = {}
        card.pos = card.pos  # lock current position
        anim = Animation(y=card.y + dp(80), opacity=0, t='out_quad', d=0.35)
        def _on_complete(anim, widget):
            if widget.parent:
                self.remove_widget(widget)
        anim.bind(on_complete=_on_complete)
        anim.start(card)

    def _show_media_card_animated(self, eid, state_dict):
        """Create media card and animate it sliding down into place."""
        state_str  = state_dict.get("state", "off")
        attributes = state_dict.get("attributes", {})
        card = HAMediaCard()
        card.size_hint = (None, None)
        card.size = (dp(340), dp(130))
        target_x = (self.width - dp(340)) / 2.0
        target_y = self.height * 0.75 - dp(65)
        card.opacity = 0
        card.pos = (target_x, target_y + dp(60))
        card.load(eid, state_str, attributes)
        self._media_card = card
        self.add_widget(card)
        anim = Animation(y=target_y, opacity=1, t='out_quad', d=0.35)
        anim.start(card)

    # ── Home Assistant media player overlay ───────────────────────────────────

    def _on_ha_state_change(self, entity_id, state_str, state_dict):
        """Called from HA listener (background thread) — reschedule on main thread."""
        if entity_id.startswith("media_player."):
            Clock.schedule_once(lambda dt: self._check_active_media(), 0)

    def _find_active_player(self):
        """Return (eid, state_dict) for the first active non-Spotify media player, or None."""
        for priority_state in ("playing", "paused", "buffering"):
            for eid, state_dict in HOME_ASSISTANT.current_states.items():
                if not eid.startswith("media_player."):
                    continue
                if state_dict.get("state") != priority_state:
                    continue
                friendly = state_dict.get("attributes", {}).get("friendly_name", "")
                if "spotify" in eid.lower() or "spotify" in friendly.lower():
                    continue
                return (eid, state_dict)
        return None

    def _check_active_media(self):
        """Show/hide the media card depending on whether any player is active."""
        if not self._splash_done:
            return
        # Don't re-show if the user has manually dismissed the card
        if self._media_card_dismissed:
            return

        active = self._find_active_player()

        if active:
            eid, state_dict = active
            state_str  = state_dict.get("state", "off")
            attributes = state_dict.get("attributes", {})
            if self._media_card is None:
                self._show_media_card_animated(eid, state_dict)
            else:
                self._media_card.update_state(state_str, attributes)
        else:
            if self._media_card is not None:
                self.remove_widget(self._media_card)
                self._media_card = None

    def on_config_update(self, config):
        self.ids.weather_widget.on_config_update(config)
        self.ids.reddit_widget.on_config_update(config)
        super().on_config_update(config)

    def on_rotary_long_pressed(self):
        self.toggle_controls()

    def on_rotary_pressed(self):
        if self._media_card is not None:
            self._media_card.do_toggle()   # play / pause
            return
        WALLPAPER_SERVICE.shuffle()

    def on_rotary_turn(self, direction, pressed):
        if self._media_card is not None:
            self._media_card.adjust_brightness(direction * 5.0)   # volume ±5%
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

            qr = QR().from_url(WALLPAPER_SERVICE.source)
            self.qr_img = NetworkImage(qr, size=(dp(256), dp(256)), pos=(dp(10), dp(10)))
            # center the qr code
            self.qr_img.pos = (dp(get_app().width - 320), dp(100))
            self.add_widget(self.qr_img)
        else:
            self.remove_widget(self.brightness_slider)
            self.brightness_slider = None
            self.remove_widget(self.banButton)
            self.banButton = None

            self.remove_widget(self.qr_img)
            self.qr_img = None