"""SpotifyScreen — Spotify playback controller for PiHome.

OAuth2 Authorization Code Flow
--------------------------------
1. User adds Client ID + Client Secret in Settings → Spotify.
2. Screen shows a two-step QR panel:
   Step 1 — scan the cert-trust QR to pre-accept PiHome's self-signed
             HTTPS certificate in the phone's browser (one-time).
   Step 2 — scan the Spotify auth QR; approving it causes Spotify to
             redirect to ``https://<pi-ip>:8989/spotify/callback``.
3. PiHome's HTTPS server catches that request, extracts the ``code`` param,
   and calls the screen's ``_handle_oauth_callback`` method via the
   generic ``server.callbacks`` registry.
4. The callback runs on the server thread, starts a background exchange
   thread that fetches access_token + refresh_token, and persists the
   refresh_token to base.ini.
5. From then on, the screen auto-refreshes the access token every 50 min
   and polls /v1/me/player every 5 seconds while visible.
"""

import base64
import time
import urllib.parse
from threading import Thread

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty, ColorProperty, NumericProperty, StringProperty,
)
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import AsyncImage, Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

try:
    import requests as _requests
except ImportError:
    _requests = None

from components.Empty.empty import Empty
from interface.pihomescreen import PiHomeScreen
from services.qr.qr import QR
from theme import theme as t
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/Spotify/spotify.kv")

# ── Constants ─────────────────────────────────────────────────────────────────
_AUTH_URL      = "https://accounts.spotify.com/authorize"
_TOKEN_URL     = "https://accounts.spotify.com/api/token"
_API_PLAYER    = "https://api.spotify.com/v1/me/player"
_SCOPES        = (
    "user-read-currently-playing "
    "user-read-playback-state "
    "user-modify-playback-state"
)
_REFRESH_SECS  = 3000   # slightly below the 3600 s token lifetime
_POLL_SECS     = 5      # playback state poll interval while on screen

# Spotify brand green
_GREEN = (0.11, 0.73, 0.33, 1.0)


def _fmt_ms(ms: int | None) -> str:
    """Format milliseconds as M:SS."""
    if not ms:
        return "0:00"
    total = ms // 1000
    return f"{total // 60}:{total % 60:02d}"


# ─────────────────────────────────────────────────────────────────────────────

class SpotifyScreen(PiHomeScreen):

    bg_color    = ColorProperty([0.07, 0.07, 0.07, 1])
    card_color  = ColorProperty([0.12, 0.12, 0.12, 1])
    text_color  = ColorProperty([1, 1, 1, 1])
    sub_color   = ColorProperty([1, 1, 1, 0.5])
    green_color = ColorProperty(list(_GREEN))

    # Playback state properties ─ bound to player widgets
    track_name    = StringProperty("No Track")
    artist_name   = StringProperty("")
    album_name    = StringProperty("")
    album_art_url = StringProperty("")
    device_name   = StringProperty("")
    is_playing    = BooleanProperty(False)
    shuffle_state = BooleanProperty(False)
    repeat_state  = StringProperty("off")   # "off" | "track" | "context"
    progress      = NumericProperty(0.0)    # 0..1
    elapsed_text  = StringProperty("0:00")
    duration_text = StringProperty("0:00")
    volume          = NumericProperty(50)
    supports_volume = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Rich dark indigo background — intentionally off-theme for Spotify branding
        self.bg_color   = [0.05, 0.04, 0.09, 1]
        self.card_color = [0.10, 0.09, 0.15, 1]
        theme = t.Theme()
        self.text_color = theme.get_color(t.Theme.TEXT_PRIMARY)
        self.sub_color  = theme.get_color(t.Theme.TEXT_SECONDARY)

        # Auth / token state — access token lives in memory only
        self._access_token: str | None = None
        self._cid   = ""
        self._csec  = ""
        self._rtok  = ""
        self._redir = ""

        # Clock handles
        self._poll_event    = None
        self._refresh_event = None

        # Volume feedback-loop guard
        self._vol_from_api = False

        # Suppress poll-based overwrite for a moment after user interaction
        self._suppress_vol_until  = 0.0
        self._suppress_prog_until = 0.0

        # Duration of the current track in ms (needed for seek calculation)
        self._dur_ms = 0

        # Widget refs for reactive updates (populated in _build_player_panel)
        self._play_btn    = None
        self._shuffle_btn = None
        self._repeat_btn  = None
        self._art         = None

        self._load_config()

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        self._cid   = CONFIG.get("spotify", "client_id",     "").strip()
        self._csec  = CONFIG.get("spotify", "client_secret", "").strip()
        self._rtok  = CONFIG.get("spotify", "refresh_token", "").strip()
        self._redir = CONFIG.get("spotify", "redirect_uri",  "").strip()
        if not self._redir:
            from util.const import SERVER_PORT
            from server.ssl_cert import lan_ip
            self._redir = f"https://{lan_ip()}:{SERVER_PORT}/spotify/callback"

    def on_config_update(self, config):
        old_cid  = self._cid
        old_csec = self._csec
        self._load_config()
        # Wipe the in-memory access token if credentials changed
        if self._cid != old_cid or self._csec != old_csec:
            self._access_token = None
        self._rebuild_content()
        super().on_config_update(config)

    # ── Screen lifecycle ──────────────────────────────────────────────────────

    def on_enter(self, *args):
        self._rebuild_content()
        return super().on_enter(*args)

    def on_leave(self, *args):
        self._stop_poll()
        from server.callbacks import unregister_callback
        unregister_callback("/spotify/callback")
        return super().on_leave(*args)

    # ── OAuth helpers ─────────────────────────────────────────────────────────

    def _build_auth_url(self) -> str:
        return _AUTH_URL + "?" + urllib.parse.urlencode({
            "response_type": "code",
            "client_id":      self._cid,
            "scope":          _SCOPES,
            "redirect_uri":   self._redir,
        })

    def _exchange_code(self, code: str):
        """Background thread: exchange auth code for tokens."""
        if not _requests:
            PIHOME_LOGGER.error("Spotify: requests library not available")
            return
        try:
            b64 = base64.b64encode(f"{self._cid}:{self._csec}".encode()).decode()
            r = _requests.post(
                _TOKEN_URL,
                data={
                    "grant_type":  "authorization_code",
                    "code":         code,
                    "redirect_uri": self._redir,
                },
                headers={"Authorization": f"Basic {b64}"},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                self._access_token = data["access_token"]
                new_rtok = data.get("refresh_token", "")
                if new_rtok:
                    self._rtok = new_rtok
                    CONFIG.set("spotify", "refresh_token", new_rtok)
                Clock.schedule_once(lambda dt: self._rebuild_content(), 0)
                PIHOME_LOGGER.info("Spotify: authorization successful")
            else:
                PIHOME_LOGGER.error(
                    f"Spotify: code exchange failed {r.status_code}: {r.text}"
                )
        except Exception as e:
            PIHOME_LOGGER.error(f"Spotify: code exchange exception: {e}")

    def _do_token_refresh(self, dt=None):
        """Schedule a background token refresh. Safe to call with or without dt."""
        if not self._rtok or not self._cid or not self._csec:
            return
        def _run():
            if not _requests:
                return
            try:
                b64 = base64.b64encode(
                    f"{self._cid}:{self._csec}".encode()
                ).decode()
                r = _requests.post(
                    _TOKEN_URL,
                    data={
                        "grant_type":    "refresh_token",
                        "refresh_token":  self._rtok,
                    },
                    headers={"Authorization": f"Basic {b64}"},
                    timeout=10,
                )
                if r.status_code == 200:
                    data = r.json()
                    self._access_token = data["access_token"]
                    new_rtok = data.get("refresh_token")
                    if new_rtok:
                        self._rtok = new_rtok
                        CONFIG.set("spotify", "refresh_token", new_rtok)
                    Clock.schedule_once(lambda _: self._on_token_ready(), 0)
                    PIHOME_LOGGER.info("Spotify: access token refreshed")
                else:
                    PIHOME_LOGGER.error(
                        f"Spotify: token refresh failed {r.status_code}"
                    )
                    self._access_token = None
            except Exception as e:
                PIHOME_LOGGER.error(f"Spotify: token refresh exception: {e}")
        Thread(target=_run, daemon=True).start()

    def _on_token_ready(self):
        """Called on main thread after a successful token refresh."""
        container = self.ids.get("content_area")
        if container is None:
            return
        # If we were showing the "reconnecting" placeholder, swap to player
        has_player = any(
            isinstance(w, BoxLayout) and getattr(w, "_spotify_player", False)
            for w in container.children
        )
        if not has_player:
            self._rebuild_content()
        else:
            self._start_poll()

    # ── Polling ───────────────────────────────────────────────────────────────

    def _start_poll(self):
        self._stop_poll()
        self._poll_event = Clock.schedule_interval(
            lambda dt: self._fetch_state(), _POLL_SECS
        )
        self._fetch_state()
        if self._refresh_event is None:
            self._refresh_event = Clock.schedule_interval(
                self._do_token_refresh, _REFRESH_SECS
            )

    def _stop_poll(self):
        if self._poll_event:
            self._poll_event.cancel()
            self._poll_event = None

    def _fetch_state(self):
        if not self._access_token:
            return
        token = self._access_token

        def _run():
            if not _requests:
                return
            try:
                r = _requests.get(
                    _API_PLAYER,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=8,
                )
                if r.status_code == 200:
                    Clock.schedule_once(lambda dt: self._apply_state(r.json()), 0)
                elif r.status_code == 204:
                    Clock.schedule_once(lambda dt: self._apply_state(None), 0)
                elif r.status_code == 401:
                    self._access_token = None
                    Clock.schedule_once(lambda dt: self._do_token_refresh(), 0)
            except Exception as e:
                PIHOME_LOGGER.error(f"Spotify: poll failed: {e}")

        Thread(target=_run, daemon=True).start()

    def _apply_state(self, data):
        if data is None:
            self.track_name    = "Nothing Playing"
            self.artist_name   = ""
            self.album_name    = ""
            self.album_art_url = ""
            self.device_name   = ""
            self.is_playing    = False
            self.progress      = 0.0
            self.elapsed_text  = "0:00"
            self.duration_text = "0:00"
            return

        item     = data.get("item") or {}
        album    = item.get("album") or {}
        images   = album.get("images") or []
        art_url  = images[0]["url"] if images else ""
        artists  = [a["name"] for a in item.get("artists", [])]
        dur_ms   = item.get("duration_ms") or 0
        prog_ms  = data.get("progress_ms") or 0

        self.track_name    = item.get("name", "Unknown")
        self.artist_name   = ", ".join(artists)
        self.album_name    = album.get("name", "")
        self.album_art_url = art_url
        self.is_playing    = data.get("is_playing", False)
        self.shuffle_state = data.get("shuffle_state", False)
        self.repeat_state  = data.get("repeat_state", "off")
        self._dur_ms       = dur_ms
        self.duration_text = _fmt_ms(dur_ms)

        # Only update progress/elapsed if the user isn't currently seeking
        if time.time() >= self._suppress_prog_until:
            self.progress     = (prog_ms / dur_ms) if dur_ms else 0.0
            self.elapsed_text = _fmt_ms(prog_ms)

        device = data.get("device") or {}
        self.device_name    = device.get("name", "")
        vol                 = device.get("volume_percent")
        self.supports_volume = bool(device.get("supports_volume", True))
        PIHOME_LOGGER.info(
            f"Spotify poll: device='{self.device_name}' vol={vol} "
            f"supports_volume={self.supports_volume} "
            f"suppressed={time.time() < self._suppress_vol_until}"
        )
        # Only update volume if the user isn't currently dragging the slider
        if vol is not None and time.time() >= self._suppress_vol_until:
            self._vol_from_api = True
            self.volume = int(vol)
            self._vol_from_api = False

    # ── Commands ──────────────────────────────────────────────────────────────

    def _cmd(self, method: str, path: str, json_body=None, params=None):
        """Fire an async Spotify API command and refresh state 0.5 s later."""
        if not self._access_token:
            return
        token = self._access_token
        url   = path if path.startswith("http") else f"{_API_PLAYER}/{path}"

        def _run():
            if not _requests:
                return
            try:
                fn = getattr(_requests, method)
                kw: dict = {
                    "headers": {"Authorization": f"Bearer {token}"},
                    "timeout": 8,
                }
                if json_body is not None:
                    kw["json"] = json_body
                if params:
                    kw["params"] = params
                resp = fn(url, **kw)
                if resp.status_code not in (200, 202, 204):
                    PIHOME_LOGGER.error(
                        f"Spotify {method.upper()} /{path} "
                        f"→ {resp.status_code}: {resp.text[:200]}"
                    )
                Clock.schedule_once(lambda dt: self._fetch_state(), 0.5)
            except Exception as e:
                PIHOME_LOGGER.error(f"Spotify cmd error: {e}")

        Thread(target=_run, daemon=True).start()

    def toggle_play_pause(self):
        self._cmd("put", "pause" if self.is_playing else "play")

    def skip_next(self):
        self._cmd("post", "next")

    def skip_prev(self):
        self._cmd("post", "previous")

    def toggle_shuffle(self):
        state = "false" if self.shuffle_state else "true"
        self._cmd("put", "shuffle", params={"state": state})

    def cycle_repeat(self):
        mapping = {"off": "context", "context": "track", "track": "off"}
        self._cmd("put", "repeat", params={"state": mapping[self.repeat_state]})

    def set_volume(self, vol: int):
        clamped = max(0, min(100, vol))
        PIHOME_LOGGER.info(f"Spotify: set_volume({clamped})")
        self._cmd("put", "volume", params={"volume_percent": clamped})

    def seek_track(self, frac: float):
        """Seek to a fractional position (0.0–1.0) in the current track."""
        if not self._dur_ms:
            return
        pos_ms = int(max(0.0, min(1.0, frac)) * self._dur_ms)
        self._cmd("put", "seek", params={"position_ms": pos_ms})

    # ── UI panels ─────────────────────────────────────────────────────────────

    def _rebuild_content(self):
        """Swap between auth-QR panel and player panel depending on state."""
        container = self.ids.get("content_area")
        if container is None:
            return
        container.clear_widgets()

        if not self._cid or not self._csec:
            container.add_widget(self._build_no_config_panel())

        elif self._access_token:
            player = self._build_player_panel()
            container.add_widget(player)
            self._start_poll()

        elif self._rtok:
            # Refresh token known — get an access token silently
            lbl = Label(
                text="Connecting to Spotify\u2026",
                font_name="Nunito",
                font_size="16sp",
                color=self.sub_color,
                halign="center",
                valign="middle",
            )
            lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            container.add_widget(lbl)
            self._do_token_refresh()

        else:
            # No tokens at all — show QR auth flow
            container.add_widget(self._build_auth_panel())
            from server.callbacks import register_callback
            register_callback("/spotify/callback", self._handle_oauth_callback)

    # ── Panel builders ────────────────────────────────────────────────────────

    def _build_no_config_panel(self) -> Widget:
        from kivy.uix.anchorlayout import AnchorLayout
        wrapper = AnchorLayout(anchor_x="center", anchor_y="center")
        wrapper.add_widget(Empty(
            icon="\u266A",
            message="Configure Spotify in Settings",
            subtitle="Add your Client ID and Client Secret",
        ))
        return wrapper

    def _build_auth_panel(self) -> BoxLayout:
        auth_url = self._build_auth_url()
        PIHOME_LOGGER.info(f"Spotify auth URL: {auth_url}")

        try:
            qr_path = QR().from_url(auth_url, "spotify_auth_qr.png")
        except Exception as e:
            PIHOME_LOGGER.error(f"Spotify: QR generation failed: {e}")
            qr_path = ""

        panel = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(12))
        panel.add_widget(Widget())

        title = Label(
            text="Connect Spotify",
            font_name="Nunito",
            font_size="22sp",
            bold=True,
            color=self.text_color,
            size_hint_y=None,
            height=dp(40),
            halign="center",
        )
        title.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        panel.add_widget(title)

        sub = Label(
            text="Scan the QR code with your phone to authorize.",
            font_name="Nunito",
            font_size="13sp",
            color=self.sub_color,
            size_hint_y=None,
            height=dp(26),
            halign="center",
        )
        sub.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        panel.add_widget(sub)

        qr_row = BoxLayout(size_hint_y=None, height=dp(200))
        qr_row.add_widget(Widget())
        qr_row.add_widget(Image(
            source=qr_path,
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None),
            size=(dp(180), dp(180)),
        ))
        qr_row.add_widget(Widget())
        panel.add_widget(qr_row)

        hint = Label(
            text=f"Waiting for callback on {self._redir}",
            font_name="Nunito",
            font_size="10sp",
            color=list(self.sub_color[:3]) + [0.4],
            size_hint_y=None,
            height=dp(22),
            halign="center",
        )
        hint.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        panel.add_widget(hint)

        panel.add_widget(Widget())
        return panel

    def _build_player_panel(self) -> BoxLayout:
        from screens.Spotify.sp_widgets import (
            SpotifyIconButton, SpotifySlider, SpotifyTextButton,
        )
        from kivy.graphics import Color as KC, Ellipse as KE

        root = BoxLayout(orientation="vertical", spacing=0, padding=0)
        root._spotify_player = True

        # ── 1. Device bar ─────────────────────────────────────────────────────
        device_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(26),
            padding=[dp(18), dp(4), dp(18), 0],
            spacing=dp(4),
        )
        dev_icon = Label(
            text="\ue307",   # Material Icons: cast
            font_name="MaterialIcons", font_size="14sp",
            color=list(_GREEN[:3]) + [0.65],
            size_hint_x=None, width=dp(20),
            halign="center", valign="middle",
        )
        dev_icon.bind(size=lambda w, s: setattr(w, "text_size", s))
        dev_lbl = Label(
            text=self.device_name,
            font_name="Nunito", font_size="11sp",
            color=list(_GREEN[:3]) + [0.65],
            halign="left", valign="middle",
            size_hint_x=None,
        )
        dev_lbl.bind(texture_size=lambda w, ts: setattr(w, "width", ts[0]))
        dev_lbl.bind(size=lambda w, s: setattr(w, "text_size", (None, s[1])))

        def _update_dev(v):
            dev_lbl.text = v
            dev_icon.opacity = 1 if v else 0
        self.bind(device_name=lambda i, v: _update_dev(v))
        _update_dev(self.device_name)

        device_bar.add_widget(Widget())
        device_bar.add_widget(dev_icon)
        device_bar.add_widget(dev_lbl)
        root.add_widget(device_bar)

        # ── 2. Album art with radial green glow ──────────────────────────────
        art_container = AnchorLayout(anchor_x="center", anchor_y="center")

        def _draw_glow(w, *_):
            w.canvas.before.clear()
            cx, cy = w.center
            r1, r2, r3 = dp(95), dp(125), dp(158)
            with w.canvas.before:
                KC(rgba=[0.11, 0.73, 0.33, 0.22])
                KE(pos=(cx - r1, cy - r1), size=(r1 * 2, r1 * 2))
                KC(rgba=[0.11, 0.73, 0.33, 0.11])
                KE(pos=(cx - r2, cy - r2), size=(r2 * 2, r2 * 2))
                KC(rgba=[0.11, 0.73, 0.33, 0.04])
                KE(pos=(cx - r3, cy - r3), size=(r3 * 2, r3 * 2))

        art_container.bind(pos=_draw_glow, size=_draw_glow)

        self._art = AsyncImage(
            source=self.album_art_url or "assets/images/audio_vinyl.png",
            allow_stretch=True, keep_ratio=True,
            size_hint=(None, None), size=(dp(210), dp(210)),
        )
        self.bind(
            album_art_url=lambda i, v: setattr(
                self._art, "source", v or "assets/images/audio_vinyl.png"
            )
        )
        art_container.add_widget(self._art)
        root.add_widget(art_container)

        # ── 3. Track / artist / album ─────────────────────────────────────────
        info = BoxLayout(
            orientation="vertical",
            size_hint_y=None, height=dp(86),
            padding=[dp(28), dp(8), dp(28), dp(4)],
            spacing=dp(3),
        )

        track_lbl = Label(
            text=self.track_name, font_name="Nunito", font_size="23sp", bold=True,
            color=self.text_color, halign="left", valign="middle",
            size_hint_y=None, height=dp(34),
        )
        track_lbl.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        self.bind(track_name=lambda i, v: setattr(track_lbl, "text", v))

        artist_lbl = Label(
            text=self.artist_name, font_name="Nunito", font_size="16sp",
            color=list(_GREEN[:3]) + [1.0], halign="left", valign="middle",
            size_hint_y=None, height=dp(26),
        )
        artist_lbl.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        self.bind(artist_name=lambda i, v: setattr(artist_lbl, "text", v))

        album_lbl = Label(
            text=self.album_name, font_name="Nunito", font_size="12sp",
            color=[1, 1, 1, 0.32], halign="left", valign="middle",
            size_hint_y=None, height=dp(18),
        )
        album_lbl.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        self.bind(album_name=lambda i, v: setattr(album_lbl, "text", v))

        info.add_widget(track_lbl)
        info.add_widget(artist_lbl)
        info.add_widget(album_lbl)
        root.add_widget(info)

        # ── 4. Progress bar ───────────────────────────────────────────────────
        prog_section = BoxLayout(
            orientation="vertical",
            size_hint_y=None, height=dp(44),
            padding=[dp(24), 0, dp(24), 0],
            spacing=dp(4),
        )
        prog_slider = SpotifySlider(
            min_val=0.0, max_val=1.0, value=self.progress,
            size_hint_y=None, height=dp(24),
        )
        self.bind(progress=lambda i, v: setattr(prog_slider, "value", v))

        # Seek on drag — debounced 0.4 s so we don't spam on every pixel
        _seek_ev = [None]
        def _on_seek_change(inst, frac):
            self._suppress_prog_until = time.time() + 3.0
            if _seek_ev[0]:
                _seek_ev[0].cancel()
            _seek_ev[0] = Clock.schedule_once(lambda dt: self.seek_track(frac), 0.4)
        prog_slider.bind(value=_on_seek_change)

        time_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(16),
        )
        elapsed_lbl = Label(
            text=self.elapsed_text, font_name="Nunito", font_size="11sp",
            color=[1, 1, 1, 0.40], halign="left", valign="middle",
        )
        elapsed_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.bind(elapsed_text=lambda i, v: setattr(elapsed_lbl, "text", v))

        dur_lbl = Label(
            text=self.duration_text, font_name="Nunito", font_size="11sp",
            color=[1, 1, 1, 0.40], halign="right", valign="middle",
        )
        dur_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.bind(duration_text=lambda i, v: setattr(dur_lbl, "text", v))

        time_row.add_widget(elapsed_lbl)
        time_row.add_widget(dur_lbl)
        prog_section.add_widget(prog_slider)
        prog_section.add_widget(time_row)
        root.add_widget(prog_section)

        # ── 5. Controls ───────────────────────────────────────────────────────
        ctrl_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(74),
            padding=[dp(14), dp(6), dp(14), dp(6)],
            spacing=0,
        )

        # Shuffle toggle
        self._shuffle_btn = SpotifyTextButton(
            text="\u21C4",
            font_size="24sp",
            active=self.shuffle_state,
            size_hint_x=None, width=dp(44),
        )
        self._shuffle_btn.bind(on_press=lambda *_: self.toggle_shuffle())
        self.bind(shuffle_state=self._update_shuffle_color)

        # Previous
        prev_btn = SpotifyIconButton(
            source="assets/icons/audio_last.png",
            size=(dp(46), dp(46)),
        )
        prev_btn.bind(on_press=lambda *_: self.skip_prev())

        # Play / Pause — larger, green-tinted
        self._play_btn = SpotifyIconButton(
            source="assets/icons/audio_pause.png" if self.is_playing
                   else "assets/icons/audio_play.png",
            size=(dp(62), dp(62)),
            color=list(_GREEN),
        )
        self._play_btn.bind(on_press=lambda *_: self.toggle_play_pause())
        self.bind(is_playing=self._update_play_icon)

        # Next
        next_btn = SpotifyIconButton(
            source="assets/icons/audio_next.png",
            size=(dp(46), dp(46)),
        )
        next_btn.bind(on_press=lambda *_: self.skip_next())

        # Repeat toggle
        rep_text = "\u21BA" if self.repeat_state == "track" else "\u21BB"
        self._repeat_btn = SpotifyTextButton(
            text=rep_text,
            font_size="24sp",
            active=self.repeat_state != "off",
            size_hint_x=None, width=dp(44),
        )
        self._repeat_btn.bind(on_press=lambda *_: self.cycle_repeat())
        self.bind(repeat_state=self._update_repeat_color)

        ctrl_row.add_widget(Widget())
        ctrl_row.add_widget(self._shuffle_btn)
        ctrl_row.add_widget(Widget())
        ctrl_row.add_widget(prev_btn)
        ctrl_row.add_widget(Widget())
        ctrl_row.add_widget(self._play_btn)
        ctrl_row.add_widget(Widget())
        ctrl_row.add_widget(next_btn)
        ctrl_row.add_widget(Widget())
        ctrl_row.add_widget(self._repeat_btn)
        ctrl_row.add_widget(Widget())
        root.add_widget(ctrl_row)

        # ── 6. Volume ─────────────────────────────────────────────────────────
        vol_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(44),
            padding=[0, dp(8), 0, dp(8)],
        )
        vol_lo = Label(
            text="\ue04d",        # Material Icons: volume_down
            font_name="MaterialIcons", font_size="20sp",
            color=[1, 1, 1, 0.45],
            size_hint_x=None, width=dp(32),
            halign="center", valign="middle",
        )
        vol_lo.bind(size=lambda w, s: setattr(w, "text_size", s))
            min_val=0, max_val=100, value=self.volume,
            size_hint_x=None, width=dp(200),
            track_height=dp(3), thumb_r=dp(6),
        )

        _vol_ev = [None]
        def _on_vol_change(inst, v):
            if not self._vol_from_api:
                self._suppress_vol_until = time.time() + 3.0
                if _vol_ev[0]:
                    _vol_ev[0].cancel()
                _vol_ev[0] = Clock.schedule_once(
                    lambda dt: self.set_volume(int(vol_slider.value)), 0.3
                )

        vol_slider.bind(value=_on_vol_change)
        self.bind(volume=lambda i, v: setattr(vol_slider, "value", v))

        vol_hi = Label(
            text="\ue050",        # Material Icons: volume_up
            font_name="MaterialIcons", font_size="20sp",
            color=[1, 1, 1, 0.45],
            size_hint_x=None, width=dp(32),
            halign="center", valign="middle",
        )
        vol_hi.bind(size=lambda w, s: setattr(w, "text_size", s))
        vol_row.add_widget(vol_lo)
        vol_row.add_widget(vol_slider)
        vol_row.add_widget(vol_hi)
        vol_row.add_widget(Widget())

        # Hide the entire row if the active device doesn't allow volume control
        def _on_supports_vol(inst, supported):
            vol_row.height   = dp(44) if supported else 0
            vol_row.opacity  = 1 if supported else 0
        self.bind(supports_volume=_on_supports_vol)
        _on_supports_vol(None, self.supports_volume)

        root.add_widget(vol_row)

        # Bottom breathing room — always present regardless of vol_row visibility
        root.add_widget(Widget(size_hint_y=None, height=dp(18)))
        return root

    # ── Rotary encoder ────────────────────────────────────────────────────────

    def on_rotary_turn(self, direction, button_pressed):
        """Spin the encoder to adjust Spotify volume by ±5."""
        step = 5 * direction
        new_vol = max(0, min(100, int(self.volume) + step))
        self.volume = new_vol
        self.set_volume(new_vol)
        return True

    def on_rotary_pressed(self):
        """Press the encoder to toggle play/pause."""
        self.toggle_play_pause()
        return True

    def on_rotary_long_pressed(self):
        """Long-press has no action on Spotify screen."""
        return True

    # ── Reactive callbacks ────────────────────────────────────────────────────

    def _update_play_icon(self, inst, is_playing):
        if self._play_btn:
            self._play_btn.source = (
                "assets/icons/audio_pause.png" if is_playing
                else "assets/icons/audio_play.png"
            )
            bw = self._play_btn._bw or dp(62)
            bh = self._play_btn._bh or dp(62)
            (
                Animation(size=(bw * 1.12, bh * 1.12), d=0.08, t="out_quad")
                + Animation(size=(bw, bh), d=0.20, t="out_back")
            ).start(self._play_btn)

    def _update_shuffle_color(self, inst, on):
        if self._shuffle_btn:
            self._shuffle_btn.active = on

    def _update_repeat_color(self, inst, state):
        if self._repeat_btn:
            self._repeat_btn.active = state != "off"
            self._repeat_btn.text = "\u21BA" if state == "track" else "\u21BB"

    # ── OAuth callback (called on server thread) ──────────────────────────────

    def _handle_oauth_callback(self, params: dict) -> str:
        """Invoked by the HTTP server when Spotify redirects to the callback URL.

        Runs on the server thread — must not touch Kivy UI directly.
        Returns HTML to display in the user's browser.
        """
        from server.callbacks import unregister_callback
        unregister_callback("/spotify/callback")  # one-shot

        error = (params.get("error") or [None])[0]
        if error:
            PIHOME_LOGGER.warning(f"Spotify: auth denied by user: {error}")
            return (
                "<h2 style='font-family:sans-serif'>Authorization denied</h2>"
                "<p style='font-family:sans-serif'>You can close this tab.</p>"
            )

        code = (params.get("code") or [None])[0]
        if not code:
            PIHOME_LOGGER.error("Spotify: callback received but no code in params")
            return "<h2 style='font-family:sans-serif'>Missing code parameter</h2>"

        Thread(target=self._exchange_code, args=(code,), daemon=True).start()
        return (
            "<h2 style='font-family:sans-serif;color:#1DB954'>Spotify connected!</h2>"
            "<p style='font-family:sans-serif'>You can close this tab and return to PiHome.</p>"
        )
