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
import urllib.parse
from threading import Thread

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty, ColorProperty, NumericProperty, StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import AsyncImage, Image
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.widget import Widget

try:
    import requests as _requests
except ImportError:
    _requests = None

from components.Button.circlebutton import CircleButton
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
    volume        = NumericProperty(50)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        theme = t.Theme()
        self.bg_color   = theme.get_color(t.Theme.BACKGROUND_PRIMARY)
        self.card_color = theme.get_color(t.Theme.BACKGROUND_SECONDARY)
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
        self.progress      = (prog_ms / dur_ms) if dur_ms else 0.0
        self.elapsed_text  = _fmt_ms(prog_ms)
        self.duration_text = _fmt_ms(dur_ms)

        device = data.get("device") or {}
        self.device_name = device.get("name", "")
        vol = device.get("volume_percent")
        if vol is not None:
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
                fn(url, **kw)
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
        self._cmd("put", "volume", params={"volume_percent": max(0, min(100, vol))})

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
        root = BoxLayout(orientation="vertical", spacing=0)
        root._spotify_player = True   # marker for _on_token_ready check

        # ── Device bar ────────────────────────────────────────────────────────
        device_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(30),
            padding=[dp(16), 0, dp(16), 0],
        )
        dev_lbl = Label(
            text=("\u25B6  " + self.device_name) if self.device_name else "",
            font_name="Nunito",
            font_size="11sp",
            color=list(_GREEN[:3]) + [0.75],
            halign="left",
            valign="middle",
        )
        dev_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.bind(
            device_name=lambda i, v: setattr(
                dev_lbl, "text", ("\u25B6  " + v) if v else ""
            )
        )
        device_bar.add_widget(dev_lbl)
        device_bar.add_widget(Widget())
        root.add_widget(device_bar)

        # ── Album art ─────────────────────────────────────────────────────────
        art_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(200),
            padding=[0, dp(4), 0, dp(4)],
        )
        self._art = AsyncImage(
            source=self.album_art_url or "assets/images/audio_vinyl.png",
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None),
            size=(dp(188), dp(188)),
        )
        self.bind(
            album_art_url=lambda i, v: setattr(
                self._art, "source", v or "assets/images/audio_vinyl.png"
            )
        )
        art_row.add_widget(Widget())
        art_row.add_widget(self._art)
        art_row.add_widget(Widget())
        root.add_widget(art_row)

        # ── Track info ────────────────────────────────────────────────────────
        info = BoxLayout(
            orientation="vertical",
            size_hint_y=None, height=dp(70),
            padding=[dp(24), dp(4), dp(24), dp(4)],
            spacing=dp(2),
        )

        track_lbl = Label(
            text=self.track_name, font_name="Nunito", font_size="17sp", bold=True,
            color=self.text_color, halign="center", valign="middle",
            size_hint_y=None, height=dp(28),
        )
        track_lbl.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        self.bind(track_name=lambda i, v: setattr(track_lbl, "text", v))

        artist_lbl = Label(
            text=self.artist_name, font_name="Nunito", font_size="13sp",
            color=self.sub_color, halign="center", valign="middle",
            size_hint_y=None, height=dp(22),
        )
        artist_lbl.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        self.bind(artist_name=lambda i, v: setattr(artist_lbl, "text", v))

        album_lbl = Label(
            text=self.album_name, font_name="Nunito", font_size="11sp",
            color=list(self.sub_color[:3]) + [0.4], halign="center", valign="middle",
            size_hint_y=None, height=dp(16),
        )
        album_lbl.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        self.bind(album_name=lambda i, v: setattr(album_lbl, "text", v))

        info.add_widget(track_lbl)
        info.add_widget(artist_lbl)
        info.add_widget(album_lbl)
        root.add_widget(info)

        # ── Progress bar ──────────────────────────────────────────────────────
        prog_col = BoxLayout(
            orientation="vertical",
            size_hint_y=None, height=dp(34),
            padding=[dp(20), 0, dp(20), 0],
            spacing=dp(2),
        )
        prog_slider = Slider(
            min=0, max=1, value=self.progress,
            size_hint_y=None, height=dp(18),
            cursor_size=(0, 0),
        )
        self.bind(progress=lambda i, v: setattr(prog_slider, "value", v))

        time_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(14))
        elapsed_lbl = Label(
            text=self.elapsed_text, font_name="Nunito", font_size="9sp",
            color=self.sub_color, halign="left", valign="middle",
        )
        elapsed_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.bind(elapsed_text=lambda i, v: setattr(elapsed_lbl, "text", v))

        dur_lbl = Label(
            text=self.duration_text, font_name="Nunito", font_size="9sp",
            color=self.sub_color, halign="right", valign="middle",
        )
        dur_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.bind(duration_text=lambda i, v: setattr(dur_lbl, "text", v))

        time_row.add_widget(elapsed_lbl)
        time_row.add_widget(dur_lbl)
        prog_col.add_widget(prog_slider)
        prog_col.add_widget(time_row)
        root.add_widget(prog_col)

        # ── Playback controls ─────────────────────────────────────────────────
        ctrl_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(76),
            padding=[dp(12), dp(8), dp(12), dp(8)],
            spacing=dp(4),
        )

        # Shuffle
        shuf_c = list(_GREEN) if self.shuffle_state else [1, 1, 1, 0.55]
        self._shuffle_btn = CircleButton(
            text="\u21C4",
            custom_font="arial-unicode-ms",
            font_size="17sp",
            size=(dp(44), dp(44)),
        )
        self._shuffle_btn.stroke_color = shuf_c
        self._shuffle_btn.text_color   = shuf_c
        self._shuffle_btn.bind(on_press=lambda *_: self.toggle_shuffle())
        self.bind(shuffle_state=self._update_shuffle_color)

        # Previous
        prev_btn = CircleButton(
            text="\u23EE",
            custom_font="arial-unicode-ms",
            font_size="19sp",
            size=(dp(50), dp(50)),
        )
        prev_btn.bind(on_press=lambda *_: self.skip_prev())

        # Play / Pause
        self._play_btn = CircleButton(
            text="\u23F8" if self.is_playing else "\u25B6",
            custom_font="arial-unicode-ms",
            font_size="22sp",
            size=(dp(60), dp(60)),
        )
        self._play_btn.stroke_color = list(_GREEN)
        self._play_btn.text_color   = list(_GREEN)
        self._play_btn.bind(on_press=lambda *_: self.toggle_play_pause())
        self.bind(is_playing=self._update_play_icon)

        # Next
        next_btn = CircleButton(
            text="\u23ED",
            custom_font="arial-unicode-ms",
            font_size="19sp",
            size=(dp(50), dp(50)),
        )
        next_btn.bind(on_press=lambda *_: self.skip_next())

        # Repeat
        rep_c    = list(_GREEN) if self.repeat_state != "off" else [1, 1, 1, 0.55]
        rep_text = "\u21BA" if self.repeat_state == "track" else "\u21BB"
        self._repeat_btn = CircleButton(
            text=rep_text,
            custom_font="arial-unicode-ms",
            font_size="17sp",
            size=(dp(44), dp(44)),
        )
        self._repeat_btn.stroke_color = rep_c
        self._repeat_btn.text_color   = rep_c
        self._repeat_btn.bind(on_press=lambda *_: self.cycle_repeat())
        self.bind(repeat_state=self._update_repeat_color)

        ctrl_row.add_widget(Widget())
        ctrl_row.add_widget(self._shuffle_btn)
        ctrl_row.add_widget(prev_btn)
        ctrl_row.add_widget(self._play_btn)
        ctrl_row.add_widget(next_btn)
        ctrl_row.add_widget(self._repeat_btn)
        ctrl_row.add_widget(Widget())
        root.add_widget(ctrl_row)

        # ── Volume slider ─────────────────────────────────────────────────────
        vol_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(44),
            padding=[dp(24), dp(8), dp(24), dp(8)],
            spacing=dp(8),
        )
        vol_low = Label(
            text="\u2212",
            font_name="Nunito",
            font_size="16sp",
            color=self.sub_color,
            size_hint_x=None,
            width=dp(20),
        )
        vol_slider = Slider(min=0, max=100, value=self.volume, size_hint_y=None, height=dp(28))

        # Only send API command when user moves the slider (not when API updates it)
        def _on_vol_change(inst, v):
            if not self._vol_from_api:
                self.set_volume(int(v))

        vol_slider.bind(value=_on_vol_change)
        self.bind(
            volume=lambda i, v: setattr(vol_slider, "value", v)
        )
        vol_high = Label(
            text="\u002B",
            font_name="Nunito",
            font_size="16sp",
            color=self.sub_color,
            size_hint_x=None,
            width=dp(20),
        )
        vol_row.add_widget(vol_low)
        vol_row.add_widget(vol_slider)
        vol_row.add_widget(vol_high)
        root.add_widget(vol_row)

        root.add_widget(Widget())  # flexible bottom spacer
        return root

    # ── Reactive callbacks ────────────────────────────────────────────────────

    def _update_play_icon(self, inst, is_playing):
        if self._play_btn:
            self._play_btn.text = "\u23F8" if is_playing else "\u25B6"
            Animation(zoom=1.15, t="out_quad", d=0.1).start(self._play_btn)

    def _update_shuffle_color(self, inst, on):
        if self._shuffle_btn:
            c = list(_GREEN) if on else [1, 1, 1, 0.55]
            self._shuffle_btn.stroke_color = c
            self._shuffle_btn.text_color   = c

    def _update_repeat_color(self, inst, state):
        if self._repeat_btn:
            c    = list(_GREEN) if state != "off" else [1, 1, 1, 0.55]
            text = "\u21BA" if state == "track" else "\u21BB"
            self._repeat_btn.stroke_color = c
            self._repeat_btn.text_color   = c
            self._repeat_btn.text = text

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
