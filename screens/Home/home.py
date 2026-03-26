import subprocess

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
from kivy.metrics import dp, sp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty, NumericProperty,ListProperty, BooleanProperty

from components.Button.circlebutton import CircleButton
from components.SmartLight.smartlight import SmartLight
from composites.Weather.weatherwidget import WeatherWidget
from composites.WaveVisualizer.wavevisualizer import WaveVisualizer
from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from listeners.ConfigurationUpdateListener import ConfigurationUpdateListener
from services.airplay.airplay import AIRPLAY
from services.audio.sfx import SFX
from services.wallpaper.wallpaper import WALLPAPER_SERVICE
from services.weather.weather import WEATHER
from composites.NowPlaying.nowplaying import NowPlayingWidget
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import appmenu_open, get_app
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

    logo_opacity = NumericProperty(0)
    logo_scale = NumericProperty(0.85)
    logo_y_offset = NumericProperty(0)

    date_time_y_offset = NumericProperty(-100)
    date_time_opacity = NumericProperty(0)
    weather_opacity = NumericProperty(0)

    weather_code = StringProperty("--")

    # ── Clock sizing (animated for Now Playing) ────────────────────────────────
    clock_font_size = NumericProperty(sp(80))
    clock_y = NumericProperty(dp(16))
    date_font_size = NumericProperty(sp(18))
    date_y = NumericProperty(dp(122))

    is_first_run = True

    # ── HA favorites panel state ──────────────────────────────────────────────
    _ha_card      = None   # currently displayed HADeviceCard widget, or None
    _ha_favorites = []     # ordered list of favorited entity_ids
    _ha_idx       = -1     # index into _ha_favorites of the displayed card (-1 = none shown)

    # ── Now Playing state ─────────────────────────────────────────────────────
    _now_playing = None          # NowPlayingWidget instance, or None
    _now_playing_art_hash = None # track cover art changes


    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.disable_rotary_press_animation = True

        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY, 0.4)
        self.size = App.get_running_app().get_size()
        Clock.schedule_interval(lambda _: self.run(), 1)
        self.on_gesture = self.handle_gesture


    def on_enter(self, *args):
        if self.is_first_run is True:
            # Hide hamburger during splash
            try:
                get_app().menu_button.disable()
            except Exception:
                pass
            # Logo fades + scales in immediately
            self._logo_intro()
            # Main reveal after loading delay
            Clock.schedule_once(lambda _: self.startup_animation(), 10)
            self.is_first_run = False

        self._start_wave_visualizer()
        AIRPLAY.register_listener(self._on_airplay_update)
        return super().on_enter(*args)

    def _logo_intro(self):
        """Fade and scale the logo in on first load."""
        intro = Animation(logo_opacity=1, logo_scale=1.0, t='out_cubic', d=1.2)
        # Gentle breathing pulse while waiting
        breathe_in = Animation(logo_scale=1.03, t='in_out_sine', d=2.5)
        breathe_out = Animation(logo_scale=0.97, t='in_out_sine', d=2.5)
        breathe = breathe_in + breathe_out
        breathe.repeat = True
        intro.bind(on_complete=lambda *_: breathe.start(self))
        self._logo_breathe = breathe
        intro.start(self)

    def on_pre_leave(self, *args):
        self._stop_wave_visualizer()
        AIRPLAY.unregister_listener(self._on_airplay_update)
        return super().on_pre_leave(*args)

    def _start_wave_visualizer(self):
        from util.configuration import CONFIG
        enabled = CONFIG.get("home", "wave_visualizer", "0").strip().lower() in ("1", "true")
        intensity = CONFIG.get("home", "wave_intensity", "Low").strip().lower()
        viz = self.ids.get('wave_visualizer')
        if viz:
            if enabled:
                viz.intensity = intensity
                viz.opacity = 1
                viz.start()
            else:
                viz.opacity = 0
                viz.stop()

    def _stop_wave_visualizer(self):
        viz = self.ids.get('wave_visualizer')
        if viz:
            viz.stop()

    def open_settings(self):
        PIHOME_SCREEN_MANAGER.goto(_SETTINGS_SCREEN)

    def open_pin(self):
        self.manager.current = 'pin'

    def startup_animation(self):
        SFX.play("startup")

        # Stop the breathing loop
        if hasattr(self, '_logo_breathe'):
            self._logo_breathe.cancel(self)

        # Phase 1: Logo lifts up and fades out
        logo_exit = Animation(
            logo_opacity=0,
            logo_y_offset=dp(40),
            logo_scale=1.05,
            t='in_out_cubic', d=0.8
        )

        # Phase 2: Date/time slides up smoothly
        dt_reveal = Animation(
            date_time_opacity=1,
            date_time_y_offset=0,
            t='out_cubic', d=0.7
        )

        # Phase 3: Weather fades in
        weather_reveal = Animation(weather_opacity=1, t='out_cubic', d=0.6)

        # Sequence: logo out → (short pause) → date/time → weather → hamburger
        def _after_logo(*args):
            Clock.schedule_once(lambda _: dt_reveal.start(self), 0.15)
            Clock.schedule_once(lambda _: weather_reveal.start(self), 0.45)
            # Re-enable the hamburger menu
            try:
                get_app().menu_button.enable()
            except Exception:
                pass

        logo_exit.bind(on_complete=_after_logo)
        logo_exit.start(self)

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
            return  # card not visible — only swipe-down should show it
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
        self.add_widget(card, index=1)

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
        self.add_widget(card, index=1)

        Animation(x=target_x, opacity=1, t='out_quad', d=0.28).start(card)

    # ── Now Playing ─────────────────────────────────────────────────────────

    def _on_airplay_update(self, airplay):
        """Listener callback from AIRPLAY service (runs on main thread)."""
        if airplay.is_playing and airplay.title:
            if self._now_playing is None:
                self._show_now_playing(airplay)
            else:
                self._update_now_playing(airplay)
        else:
            if self._now_playing is not None:
                self._hide_now_playing()

    def _show_now_playing(self, airplay):
        """Create the Now Playing card and animate it in, shrinking the clock."""
        card = NowPlayingWidget()
        card.update_data(airplay)
        card.set_cover_art(airplay.cover_art_bytes)
        self._now_playing_art_hash = id(airplay.cover_art_bytes)

        card.pos = (dp(16), dp(16))
        card.opacity = 0
        self._now_playing = card
        self.add_widget(card, index=1)

        # Shrink clock and slide it up
        clock_anim = Animation(
            clock_font_size=sp(50), clock_y=dp(110),
            date_font_size=sp(13), date_y=dp(170),
            t='out_cubic', d=0.3,
        )
        clock_anim.start(self)

        # Fade card in with slight upward slide
        card.y = dp(6)
        Animation(y=dp(16), opacity=1, t='out_cubic', d=0.3).start(card)

    def _update_now_playing(self, airplay):
        """Update the existing Now Playing card with new metadata."""
        if self._now_playing is None:
            return
        self._now_playing.update_data(airplay)
        # Only rebuild texture if cover art actually changed
        art_id = id(airplay.cover_art_bytes)
        if art_id != self._now_playing_art_hash:
            self._now_playing_art_hash = art_id
            self._now_playing.set_cover_art(airplay.cover_art_bytes)

    def _hide_now_playing(self):
        """Fade out the Now Playing card and restore the clock."""
        card = self._now_playing
        if card is None:
            return
        self._now_playing = None
        self._now_playing_art_hash = None

        # Restore clock size
        clock_anim = Animation(
            clock_font_size=sp(80), clock_y=dp(16),
            date_font_size=sp(18), date_y=dp(122),
            t='out_cubic', d=0.3,
        )
        clock_anim.start(self)

        # Fade card out
        fade = Animation(y=dp(6), opacity=0, t='in_cubic', d=0.3)

        def _on_done(anim, widget):
            if widget.parent:
                self.remove_widget(widget)

        fade.bind(on_complete=_on_done)
        fade.start(card)

    # ── Config / lifecycle ────────────────────────────────────────────────────

    def on_config_update(self, config):
        self.ids.weather_widget.on_config_update(config)
        self.ids.reddit_widget.on_config_update(config)
        if self._now_playing is not None:
            self._now_playing.update_theme()
        if self.is_open:
            self._start_wave_visualizer()
        super().on_config_update(config)

    # ── Rotary encoder ────────────────────────────────────────────────────────

    def on_rotary_pressed(self):
        if self._ha_card is not None:
            self._ha_card.do_toggle()
            return
        WALLPAPER_SERVICE.shuffle()

    def on_rotary_turn(self, direction, pressed):
        if self._ha_card is not None:
            self._ha_card.adjust_brightness(direction * 5.0)
            return
        if direction == 1:
            WALLPAPER_SERVICE.next()
        elif direction == -1:
            WALLPAPER_SERVICE.previous()

