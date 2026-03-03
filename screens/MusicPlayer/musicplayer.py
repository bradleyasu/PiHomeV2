"""
screens/MusicPlayer/musicplayer.py

Redesigned MusicPlayer screen.

Layout
------
Left panel (42 %): large album art centred over an ambient vinyl shader.
Right panel (58 %): song title, status badge, volume bar and action buttons.
Bottom drawer: saved radio-station carousel that slides up on demand.

Rotary encoder
--------------
  Turn (drawer closed) : volume up/down
  Turn (drawer open)   : navigate stations
  Press                : toggle drawer  (if drawer open + station loaded → play)
  Long-press           : stop audio  /  close drawer without playing
"""

import time as _time
from datetime import datetime

import numpy as np

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import BindTexture, RenderContext
from kivy.graphics.texture import Texture
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty, ColorProperty, ListProperty,
    NumericProperty, ObjectProperty, StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout

from components.Image.networkimage import NetworkImage  # noqa – registers kv rule
from interface.pihomescreen import PiHomeScreen
from screens.MusicPlayer.musicvolumebar import MusicVolumeBar  # noqa – registers kv rule
from screens.MusicPlayer.shaders import sVINYL
from services.audio.audioplayernew import AUDIO_PLAYER, AudioState
from theme.theme import Theme

Builder.load_file("./screens/MusicPlayer/musicplayer.kv")

# ── Fixed dark palette for the immersive player experience ───────────────────
_BG_DARK   = (0.05, 0.06, 0.09, 1.0)
_BG_PANEL  = (0.09, 0.10, 0.15, 1.0)
_BG_CARD   = (0.13, 0.15, 0.22, 1.0)
_TEXT      = (1.0,  1.0,  1.0,  0.95)
_MUTED     = (1.0,  1.0,  1.0,  0.42)


# ─────────────────────────────────────────────────────────────────────────────
class MusicPlayerContainer(PiHomeScreen):
    """Root screen widget — manages layout, clock, and rotary encoder."""

    current_time = StringProperty("--:-- --")
    bg_color     = ColorProperty(_BG_DARK)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.disable_rotary_press_animation = True

        self.player = Player(radio_cb=self._toggle_drawer)
        self.drawer = RadioDrawer()

        self.add_widget(self.player)
        self.add_widget(self.drawer)

        Clock.schedule_interval(lambda _: self._tick(), 1)

    # ── clock ──────────────────────────────────────────────────────────────────

    def _tick(self):
        now = datetime.now().strftime("%I:%M %p")
        self.current_time = now
        self.player.current_time = now

    # ── drawer helpers ────────────────────────────────────────────────────────

    def _toggle_drawer(self):
        self.drawer.is_open = not self.drawer.is_open

    # ── rotary ────────────────────────────────────────────────────────────────

    def on_rotary_turn(self, direction, button_pressed):
        if self.drawer.is_open:
            if direction == 1:
                self.drawer.next_station()
            else:
                self.drawer.prev_station()
        else:
            # Default: volume up / down
            return super().on_rotary_turn(direction, button_pressed)

    def on_rotary_pressed(self):
        if self.drawer.is_open:
            # Press while drawer is open → play selection & dismiss
            self.drawer.play_current()
        else:
            # Press while drawer is closed → open the drawer
            self.drawer.is_open = True
        return None

    def on_rotary_long_pressed(self):
        if self.drawer.is_open:
            self.drawer.is_open = False
        else:
            self.player.stop()
        return None


# ─────────────────────────────────────────────────────────────────────────────
class Player(BoxLayout):
    """
    Main player layout (horizontal):
      left 42 %  — VinylWidget backdrop + album art
      right 58 % — title, status, volume, controls
    """

    now_playing   = StringProperty("Nothing Playing")
    album_art    = StringProperty("")
    status_text  = StringProperty("")       # "PLAYING" | "BUFFERING" | etc.
    is_playing   = BooleanProperty(False)
    current_time = StringProperty("--:-- --")

    def __init__(self, radio_cb=None, **kwargs):
        super().__init__(**kwargs)
        self._radio_cb = radio_cb
        # KV rules are applied before __init__ body after super() — ids are live
        Clock.schedule_once(self._post_init, 0)

    def _post_init(self, _dt):
        """Deferred init: set up shader and register audio listeners."""
        if hasattr(self.ids, 'vinyl_widget'):
            self.ids.vinyl_widget.fs = sVINYL
        AUDIO_PLAYER.add_volume_listener(self._on_volume)
        AUDIO_PLAYER.add_state_listener(self._on_state)
        AUDIO_PLAYER.add_saves_listener(self._on_saves)
        # Sync initial volume
        self._on_volume(AUDIO_PLAYER.volume)

    # ── public interface ──────────────────────────────────────────────────────

    def set_volume(self, v):
        AUDIO_PLAYER.set_volume(v)

    def stop(self):
        AUDIO_PLAYER.stop(clear_playlist=True)

    def save_song(self):
        AUDIO_PLAYER.save_current()

    def open_stations(self):
        if self._radio_cb:
            self._radio_cb()

    # ── private listeners ─────────────────────────────────────────────────────

    def _on_volume(self, v):
        vb = self.ids.get("volume_bar")
        if vb:
            vb.value = max(0.0, min(1.0, float(v)))

    def _on_state(self, state):
        self.is_playing = False

        if state == AudioState.PLAYING:
            self._on_saves()
            title = AUDIO_PLAYER.title or "Unknown"
            self.now_playing = (title[:30] + "…") if len(title) > 30 else title
            self.album_art   = AUDIO_PLAYER.album_art or ""
            self.is_playing  = True
            self.status_text = "PLAYING"

        elif state == AudioState.STOPPED:
            self.album_art   = ""
            self.now_playing = "Nothing Playing"
            self.status_text = ""
            # Reset the heart icon
            fb = self.ids.get("fav_button")
            if fb:
                fb.text = '\ue87e'

        elif state == AudioState.FETCHING:
            self.now_playing = "Fetching…"
            self.status_text = "FETCHING"

        elif state == AudioState.BUFFERING:
            self.now_playing = "Buffering…"
            self.status_text = "BUFFERING"

    def _on_saves(self, *_):
        fb = self.ids.get("fav_button")
        if fb is None or AUDIO_PLAYER.current_source is None:
            return
        saved = AUDIO_PLAYER.save_exists(AUDIO_PLAYER.current_source)
        # \ue87d = favorite (filled heart)   \ue87e = favorite_border (outline)
        fb.text = '\ue87d' if saved else '\ue87e'


# ─────────────────────────────────────────────────────────────────────────────
class RadioDrawer(BoxLayout):
    """
    Bottom-anchored slide-up panel for saved radio stations.

    Closed: y = -DRAWER_H  (off-screen below)
    Open  : y = 0           (bottom of the screen)
    """

    is_open  = BooleanProperty(False)
    content  = ListProperty([])

    _DRAWER_H = None   # set lazily on first use to avoid premature dp calls

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._DRAWER_H = dp(168)
        self.size_hint = (1, None)
        self.height    = self._DRAWER_H
        self.x         = 0
        self.y         = -self._DRAWER_H   # start hidden below screen
        self.refresh()

    # ── open / close ──────────────────────────────────────────────────────────

    def on_is_open(self, _instance, value):
        if value:
            self.content = list(AUDIO_PLAYER.saved_urls)
            Animation(y=0, d=0.30, t='out_cubic').start(self)
        else:
            Animation(y=-self._DRAWER_H, d=0.24, t='in_cubic').start(self)

    # ── carousel control ──────────────────────────────────────────────────────

    def next_station(self):
        c = self.ids.get("radio_carousel")
        if c:
            c.load_next()

    def prev_station(self):
        c = self.ids.get("radio_carousel")
        if c:
            c.load_previous()

    def play_current(self):
        c = self.ids.get("radio_carousel")
        if c and c.current_slide:
            self._play(c.current_slide.url)

    def _play(self, url):
        AUDIO_PLAYER.play(url)
        self.is_open = False

    # ── content ───────────────────────────────────────────────────────────────

    def on_content(self, *_):
        self.refresh()

    def refresh(self):
        c = self.ids.get("radio_carousel")
        if c is None:
            return
        c.clear_widgets()
        for item in self.content:
            card = RadioCard(
                station_name=item.get("text", ""),
                url=item.get("url", ""),
                thumbnail=item.get("thumbnail") or "",
                on_press=self._make_cb(item.get("url", "")),
            )
            c.add_widget(card)

    def _make_cb(self, url):
        return lambda *_: self._play(url)

    # ── touch: dismiss on tap-outside ─────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            super().on_touch_down(touch)
            return True
        if self.is_open:
            self.is_open = False
            return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
class RadioCard(ButtonBehavior, BoxLayout):
    """Individual station card shown in the RadioDrawer carousel."""

    station_name = StringProperty("")
    thumbnail    = StringProperty("")
    url          = StringProperty("")

    def __init__(self, station_name="", url="", thumbnail="", **kwargs):
        super().__init__(**kwargs)
        text = station_name
        self.station_name = (text[:14] + "…") if len(text) > 14 else text
        self.url          = url
        self.thumbnail    = thumbnail or "screens/MusicPlayer/default_album_art.png"


# ─────────────────────────────────────────────────────────────────────────────
# VinylWidget — audio-reactive OpenGL vinyl record visualizer (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
class VinylWidget(FloatLayout):
    fs           = StringProperty(None, allownone=True)
    audio_texture = ObjectProperty(None)
    xOffset      = NumericProperty(0)
    yOffset      = NumericProperty(0)
    bar_count    = 12

    def __init__(self, **kwargs):
        self.canvas = RenderContext(
            use_parent_projection=True,
            use_parent_modelview=True,
            use_parent_frag_modelview=False,
        )
        super().__init__(**kwargs)
        Clock.schedule_interval(self.update_glsl, 1 / 60.0)
        self.audio_texture = Texture.create(
            size=(self.bar_count, 2), colorfmt='luminance'
        )
        with self.canvas:
            BindTexture(texture=self.audio_texture, index=1)

    def on_fs(self, _instance, value):
        shader = self.canvas.shader
        old = shader.fs
        shader.fs = value
        if not shader.success:
            shader.fs = old
            raise Exception('VinylWidget: shader compilation failed')

    def update_glsl(self, *_):
        self.canvas['time']       = Clock.get_boottime()
        self.canvas['resolution'] = list(map(float, self.size))
        self.canvas['offsetX']    = self.xOffset
        self.canvas['offsetY']    = self.yOffset
        self.canvas['volume']     = AUDIO_PLAYER.volume

        if AUDIO_PLAYER.data and AUDIO_PLAYER.current_state == AudioState.PLAYING:
            arr = np.frombuffer(AUDIO_PLAYER.data, dtype=np.float32)
            self.audio_texture.blit_buffer(arr.tobytes(), colorfmt='luminance', bufferfmt='float')
        else:
            self.audio_texture.blit_buffer(
                np.zeros(AUDIO_PLAYER.buffersize, dtype=np.float32).tobytes(),
                colorfmt='luminance', bufferfmt='float',
            )
        self._bind_channel()

    def _bind_channel(self):
        self.audio_texture.bind()
        self.canvas['texture1'] = 1
        self.canvas.ask_update()

