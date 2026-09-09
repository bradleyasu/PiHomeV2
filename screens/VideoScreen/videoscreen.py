"""Full-screen video playback driven entirely by the VideoEvent.

Hidden from the app menu: nothing navigates here by hand. A ``video`` event
arrives over MQTT/HTTP/WebSocket, this screen becomes current, resolves the
source on a worker thread and plays it.

Rendering follows BambuLab's camera pattern -- decode off the UI path, blit
into a ``Texture``, bind it to a KV ``Rectangle`` -- but the decoder is libmpv
rather than ffpyplayer, because only mpv can play yt-dlp's separate video and
audio URLs as one synchronised timeline and target a specific ALSA device.
See player.py for the full rationale.
"""

import threading

from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty, ColorProperty, NumericProperty, ObjectProperty, StringProperty,
)

from interface.pihomescreen import PiHomeScreen
from theme.theme import Theme
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

from screens.VideoScreen import player as vplayer
from screens.VideoScreen import resolver

Builder.load_file("./screens/VideoScreen/videoscreen.kv")

_th = Theme()


class VideoScreenScreen(PiHomeScreen):
    """Plays a video full screen, then returns to the previous screen."""

    # Video is always letterboxed against black regardless of theme -- mpv
    # draws the bars itself -- but the status/error text follows the theme.
    bg_color     = ColorProperty((0, 0, 0, 1))
    text_color   = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color  = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    accent_color = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))

    video_texture = ObjectProperty(None, allownone=True)
    status_text   = StringProperty("")
    title_text    = StringProperty("")
    show_status   = BooleanProperty(True)
    progress      = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set by VideoEvent immediately before goto().
        self.source = ""
        self.audio_device = ""
        self.timeout = 0
        self.loop = False
        self.max_height_override = 0   # per-event `quality`, 0 = use [video]

        self._player = None
        self._tex = None
        self._tick_ev = None
        self._timeout_ev = None
        self._resolve_thread = None
        self._stop_event = threading.Event()
        self._generation = 0     # invalidates in-flight resolves after a stop
        self._blit_bytes = False  # set if this Kivy build rejects a memoryview
        self._load_config()

    # ── Configuration ────────────────────────────────────────────────────────

    def _load_config(self):
        """Read [video] from base.ini.

        This screen is hidden, and screens/Settings/settings.py skips hidden
        manifests, so there is no Settings panel -- these are edited in
        base.ini and every one of them can be overridden per event.
        """
        self._max_height     = CONFIG.get_int("video", "max_height", 480)
        self._default_device = CONFIG.get("video", "audio_device", "auto").strip()
        self._hwdec          = CONFIG.get("video", "hwdec", "auto-safe").strip()
        self._cache_secs     = CONFIG.get_int("video", "cache_secs", 20)
        self._ytdlp          = CONFIG.get("video", "ytdlp_path", "yt-dlp").strip() or "yt-dlp"
        self._resolve_secs   = CONFIG.get_int("video", "resolve_timeout", 45)
        self._volume         = CONFIG.get_int("video", "volume", 100)
        self._cookies        = CONFIG.get("video", "cookies_file", "").strip() or None
        self._vid_w          = CONFIG.get_int("window", "width", 800)
        self._vid_h          = CONFIG.get_int("window", "height", 480)

    def on_config_update(self, config):
        self._load_config()
        super().on_config_update(config)
        # The theme cascade would repaint the letterbox area; keep it black.
        self.bg_color = (0, 0, 0, 1)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_enter(self, *args):
        super().on_enter(*args)
        self._load_config()
        # A lazily-themed screen misses the startup reload_all(), so apply the
        # theme before anything renders (CLAUDE.md gotcha #13).
        super().on_config_update(CONFIG)
        self.bg_color = (0, 0, 0, 1)
        self._begin()
        return None

    def on_pre_leave(self, *args):
        self._teardown()
        return super().on_pre_leave(*args)

    # ── Resolve then play ────────────────────────────────────────────────────

    def _begin(self):
        self._stop_event.clear()
        self._generation += 1
        generation = self._generation

        self.video_texture = None
        self.progress = 0.0
        self.title_text = ""
        self.show_status = True

        playable, why = vplayer.check_playable()
        if not playable:
            self._fail(why or "Player unavailable")
            return
        if not self.source:
            self._fail("No video source given")
            return

        ok, message = vplayer.probe_hardware_decode()
        (PIHOME_LOGGER.info if ok else PIHOME_LOGGER.warn)("VideoScreen: {}".format(message))

        kind = resolver.classify(self.source)
        self.status_text = "Loading..." if kind != resolver.EXTRACT else "Resolving..."

        if self.timeout and self.timeout > 0:
            self._timeout_ev = Clock.schedule_once(
                lambda dt: self._finish("timeout"), float(self.timeout)
            )

        self._resolve_thread = threading.Thread(
            target=self._resolve_worker, args=(self.source, generation),
            daemon=True, name="videoscreen-resolve",
        )
        self._resolve_thread.start()

    def _resolve_worker(self, source, generation):
        max_height = self.max_height_override or self._max_height
        try:
            result = resolver.resolve(
                source, max_height=max_height, ytdlp=self._ytdlp,
                timeout=self._resolve_secs, cookies=self._cookies,
            )
        except Exception as e:
            PIHOME_LOGGER.error("VideoScreen: resolve failed: {}".format(e))
            Clock.schedule_once(
                lambda dt, m=str(e), g=generation: self._fail(m, g), 0
            )
            return
        Clock.schedule_once(
            lambda dt, r=result, g=generation: self._play(r, g), 0
        )

    def _play(self, result, generation):
        """Start playback on the main thread. Ignored if the screen moved on."""
        if generation != self._generation or self._stop_event.is_set():
            return
        self.title_text = result.title or ""
        self.status_text = "Buffering..."

        device = (self.audio_device or "").strip() or self._default_device
        player = vplayer.VideoPlayer(
            self._vid_w, self._vid_h,
            on_end=lambda reason, g=generation: Clock.schedule_once(
                lambda dt: self._on_end(reason, g), 0),
            on_error=lambda message, g=generation: Clock.schedule_once(
                lambda dt: self._fail(message, g), 0),
        )
        try:
            player.start(
                result, audio_device=device, hwdec=self._hwdec,
                cache_secs=self._cache_secs, volume=self._volume, loop=self.loop,
            )
        except Exception as e:
            PIHOME_LOGGER.error("VideoScreen: playback failed: {}".format(e))
            self._fail(str(e), generation)
            return

        self._player = player
        self._tick_ev = Clock.schedule_interval(self._tick, 0)

    # ── Frame pump ───────────────────────────────────────────────────────────

    def _tick(self, dt):
        player = self._player
        if player is None:
            return False
        buf = player.render_frame()
        if buf is None:
            return None
        self._blit(buf)
        if self.show_status:
            # First frame is on screen; drop the status overlay.
            self.show_status = False
            self.status_text = ""
        duration = player.duration
        self.progress = (player.position / duration) if duration > 0 else 0.0
        return None

    def _blit(self, buf):
        try:
            if self._tex is None or self._tex.size != (self._vid_w, self._vid_h):
                self._tex = Texture.create(
                    size=(self._vid_w, self._vid_h), colorfmt="rgba"
                )
                # mpv's software renderer writes the top row first, but a plain
                # canvas Rectangle maps buffer row 0 to the BOTTOM of the quad,
                # so the frame arrives upside down without this. (RoundedRectangle
                # maps the other way round, which is why the gradient helper in
                # components/Button/simplebutton.py needs no flip.) BambuLab's
                # camera texture flips for the same reason.
                self._tex.flip_vertical()
            if self._blit_bytes:
                buf = bytes(buf)
            self._tex.blit_buffer(buf, colorfmt="rgba", bufferfmt="ubyte")
        except TypeError:
            # Older Kivy builds only accept bytes, not a memoryview.
            self._blit_bytes = True
            try:
                self._tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
            except Exception as e:
                PIHOME_LOGGER.error("VideoScreen: blit failed: {}".format(e))
                return
        except Exception as e:
            PIHOME_LOGGER.error("VideoScreen: blit failed: {}".format(e))
            return

        self.video_texture = self._tex
        # blit_buffer mutates the texture in place, so the ObjectProperty sees
        # no change and KV never repaints. Force the dispatch (as BambuLab does).
        self.property("video_texture").dispatch(self)

    # ── Termination ──────────────────────────────────────────────────────────

    def _on_end(self, reason, generation):
        if generation != self._generation:
            return
        self._finish(reason or "eof")

    def _fail(self, message, generation=None):
        if generation is not None and generation != self._generation:
            return
        self.show_status = True
        self.status_text = message or "Playback failed"
        PIHOME_LOGGER.error("VideoScreen: {}".format(self.status_text))
        # Leave the message up briefly so it is readable, then return.
        Clock.schedule_once(lambda dt: self._finish("error"), 4)

    def _finish(self, reason):
        PIHOME_LOGGER.info("VideoScreen: finished ({})".format(reason))
        self._teardown()
        self.go_back()

    def _teardown(self):
        self._generation += 1
        self._stop_event.set()
        if self._tick_ev is not None:
            self._tick_ev.cancel()
            self._tick_ev = None
        if self._timeout_ev is not None:
            self._timeout_ev.cancel()
            self._timeout_ev = None
        player, self._player = self._player, None
        if player is not None:
            player.stop()
        self.video_texture = None
        self._tex = None
        self.progress = 0.0
        self.show_status = True
        self.status_text = ""
        self.title_text = ""

    def stop_playback(self):
        """Called by the video_stop event."""
        self._finish("stopped")

    # ── Input ────────────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        """Tap toggles pause.

        Deliberately not 'tap exits' (as DisplayImageEvent does) -- an
        accidental brush should not kill a video. The hamburger menu and the
        rotary long-press both still leave the screen.
        """
        if self._player is not None and self.collide_point(*touch.pos):
            self._player.toggle_pause()
            return True
        return super().on_touch_down(touch)

    def on_rotary_turn(self, direction, button_pressed):
        """Knob adjusts volume; held-and-turned scrubs."""
        if self._player is None:
            return False
        if button_pressed:
            self._player.seek(10 * direction)
        else:
            self._player.nudge_volume(5 * direction)
        return True

    def on_rotary_pressed(self):
        if self._player is None:
            return False
        self._player.toggle_pause()
        return True

    def on_rotary_long_pressed(self):
        self._finish("dismissed")
        return True
