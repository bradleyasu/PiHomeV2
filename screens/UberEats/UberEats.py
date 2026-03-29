import time
import requests
from threading import Thread

from kivy.clock import Clock
from kivy.graphics import Color as KColor, RoundedRectangle as KRR, Rectangle as KRect
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ColorProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from components.Empty.empty import Empty
from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from services.audio.sfx import SFX
from theme.theme import Theme
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/UberEats/UberEats.kv")

# Uber Eats internal web endpoint (session-cookie authenticated)
_API_URL = "https://www.ubereats.com/api/getActiveOrdersV1"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
# Brand green used in Uber Eats UI
_BRAND_GREEN = (0.02, 0.93, 0.49, 1.0)


class UberEatsScreen(PiHomeScreen):
    """
    Uber Eats live order tracker.

    Authentication note: Uber Eats has no official consumer-facing API.
    This screen accesses the same internal endpoint the website uses.
    To authenticate, open ubereats.com in a browser, go to DevTools →
    Network → find the 'getActiveOrdersV1' request → copy the 'cookie'
    and 'x-csrf-token' request header values into Settings here.
    Session cookies expire; when tracking stops working, paste fresh values.
    """

    # ── Theme ─────────────────────────────────────────────────────
    bg_color     = ColorProperty([0, 0, 0, 1])
    header_color = ColorProperty([0, 0, 0, 1])
    card_color   = ColorProperty([0, 0, 0, 0.85])
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([0.5, 0.5, 0.5, 1])
    accent_color = ColorProperty([0.36, 0.67, 1.0, 1])
    brand_color  = ColorProperty(list(_BRAND_GREEN))

    # ── Order state ───────────────────────────────────────────────
    order_active    = BooleanProperty(False)
    restaurant_name = StringProperty("Uber Eats")
    status_text     = StringProperty("")
    eta_text        = StringProperty("")
    phase_text      = StringProperty("")
    progress        = NumericProperty(0)   # 0–5 matching progress ticks
    hero_image      = StringProperty("")

    # ── Map coordinates ───────────────────────────────────────────
    marker_lat = NumericProperty(0)
    marker_lon = NumericProperty(0)
    store_lat  = NumericProperty(0)
    store_lon  = NumericProperty(0)
    home_lat   = NumericProperty(0)
    home_lon   = NumericProperty(0)

    # ── Internal ──────────────────────────────────────────────────
    _cookie      = ""
    _csrf_token  = ""
    _locale      = "en-US"
    _poll_start  = 17
    _poll_end    = 23
    _poll_event  = None
    is_visible   = False
    _mapview     = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        theme = Theme()
        self.bg_color     = theme.get_color(theme.BACKGROUND_PRIMARY)
        self.header_color = theme.get_color(theme.BACKGROUND_SECONDARY)
        self.text_color   = theme.get_color(theme.TEXT_PRIMARY)
        self.muted_color  = theme.get_color(theme.TEXT_SECONDARY)
        self.accent_color = theme.get_color(theme.ALERT_INFO)
        hc = self.header_color
        self.card_color   = (hc[0], hc[1], hc[2], 0.85)

        self._load_config()
        # Build empty content on first frame once ids are available
        Clock.schedule_once(self._initial_build, 0)

    # ── Config ────────────────────────────────────────────────────

    def _load_config(self):
        self._cookie     = CONFIG.get('ubereats', 'cookie', '')
        self._csrf_token = CONFIG.get('ubereats', 'csrf_token', '')
        self._locale     = CONFIG.get('ubereats', 'locale', 'en-US')
        try:
            self._poll_start = int(CONFIG.get('ubereats', 'poll_start_hour', '17'))
            self._poll_end   = int(CONFIG.get('ubereats', 'poll_end_hour', '23'))
        except (ValueError, TypeError):
            self._poll_start = 17
            self._poll_end   = 23

    def on_config_update(self, config):
        self._load_config()
        self._poll()
        super().on_config_update(config)

    # ── Screen lifecycle ──────────────────────────────────────────

    def on_enter(self, *args):
        self.is_visible = True
        if not self._poll_event:
            self._poll_event = Clock.schedule_interval(lambda _: self._maybe_poll(), 60)
        self._poll()
        return super().on_enter(*args)

    def on_leave(self, *args):
        self.is_visible = False
        if self._poll_event:
            self._poll_event.cancel()
            self._poll_event = None
        return super().on_leave(*args)

    # ── Polling ───────────────────────────────────────────────────

    def _maybe_poll(self):
        if not self._cookie:
            return
        hour = int(time.strftime("%H"))
        if self.is_visible or (self._poll_start <= hour <= self._poll_end):
            self._poll()

    def _poll(self):
        if not self._cookie:
            PIHOME_LOGGER.warn("UberEats: session cookie not configured — add it in Settings")
            return

        def _fetch():
            try:
                with requests.post(
                    _API_URL,
                    params={'localeCode': self._locale},
                    headers={
                        'cookie':        self._cookie,
                        'x-csrf-token':  self._csrf_token,
                        'user-agent':    _USER_AGENT,
                        'accept':        'application/json',
                        'content-type':  'application/json',
                    },
                    timeout=15,
                ) as resp:
                    if resp.status_code == 200:
                        data = resp.json()
                        Clock.schedule_once(lambda dt, d=data: self._apply(d), 0)
                    else:
                        PIHOME_LOGGER.error(
                            "UberEats: HTTP {} — session cookie may have expired".format(
                                resp.status_code))
            except Exception as e:
                PIHOME_LOGGER.error("UberEats: request failed: {}".format(e))

        Thread(target=_fetch, daemon=True).start()

    def _apply(self, data):
        try:
            orders = data.get('data', {}).get('orders', [])
            orders = [o for o in orders
                      if o.get('orderInfo', {}).get('orderPhase') != 'COMPLETED']
        except Exception as e:
            PIHOME_LOGGER.error("UberEats: parse error: {}".format(e))
            return

        if not orders:
            self.order_active    = False
            self.restaurant_name = "Uber Eats"
            self.status_text     = ""
            self.eta_text        = ""
            self.phase_text      = ""
            self.progress        = 0
            self.hero_image      = ""
            return

        was_active = self.order_active
        try:
            order      = orders[0]
            order_info = order['orderInfo']
            store_info = order_info['storeInfo']
            overview   = order.get('activeOrderOverview', {})
            status     = order.get('activeOrderStatus')

            self.restaurant_name = store_info.get(
                'name', overview.get('title', 'Your Order'))
            self.hero_image = store_info.get('heroImageURL', '')
            self.store_lat  = store_info.get('location', {}).get('latitude', 0)
            self.store_lon  = store_info.get('location', {}).get('longitude', 0)

            if status:
                self.status_text = (status.get('titleSummary', {})
                                    .get('summary', {}).get('text', ''))
                self.eta_text    = status.get('title', '')
                self.progress    = int(status.get('currentProgress', 0))

            self.phase_text = (order_info.get('orderPhase', '')
                               .replace('_', ' ').title())

            feed_cards = order.get('backgroundFeedCards', [])
            if feed_cards:
                entities = feed_cards[0].get('mapEntity', [])
                if len(entities) >= 1:
                    self.marker_lat = entities[0].get('latitude', 0)
                    self.marker_lon = entities[0].get('longitude', 0)
                if len(entities) >= 2:
                    self.home_lat = entities[1].get('latitude', 0)
                    self.home_lon = entities[1].get('longitude', 0)

            self.order_active = True

            # First detection: chime + navigate to this screen
            if not was_active:
                SFX.play("long_notify")
                PIHOME_SCREEN_MANAGER.goto(self.name)

        except Exception as e:
            PIHOME_LOGGER.error("UberEats: apply error: {}".format(e))

    def refresh(self):
        """Manual refresh — exposed for rotary press or external call."""
        self._poll()

    # ── UI construction ───────────────────────────────────────────

    def _initial_build(self, dt):
        self._rebuild_content()

    def on_order_active(self, instance, value):
        self._rebuild_content()
        if value and self._mapview and self.marker_lat:
            self._mapview.center_on(self.marker_lat, self.marker_lon)

    def on_marker_lat(self, instance, value):
        if self._mapview and value:
            self._mapview.center_on(value, self.marker_lon)

    def _rebuild_content(self):
        content = self.ids.get('content_area')
        if content is None:
            return
        # Unbind old mapview if present
        self._mapview = None
        content.clear_widgets()
        if self.order_active:
            self._build_active_panel(content)
        else:
            self._build_empty_panel(content)

    def _build_empty_panel(self, parent):
        sub_text = (
            "Add your session cookie in Settings to start tracking"
            if not self._cookie
            else "Checking for active orders every 60 seconds"
        )
        empty = Empty(
            icon="\u2298",          # ⊘ — BMP-safe, renders in ArialUnicode
            message="No Active Orders",
            subtitle=sub_text,
            size=(parent.width or 480, parent.height or 360),
        )
        parent.bind(
            width=lambda _, v: setattr(empty, 'size', (v, empty.height)),
            height=lambda _, v: setattr(empty, 'size', (empty.width, v)),
        )
        parent.add_widget(empty)

    def _build_active_panel(self, parent):
        # ── Hero image ─────────────────────────────────────────────
        hero = AsyncImage(
            source=self.hero_image,
            size_hint_y=None, height=dp(150),
            allow_stretch=True, keep_ratio=False,
        )
        self.bind(hero_image=lambda _, v: setattr(hero, 'source', v))
        parent.add_widget(hero)

        # ── Status card ────────────────────────────────────────────
        status_card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(82),
            padding=[dp(16), dp(10), dp(16), dp(10)],
            spacing=dp(8),
        )
        with status_card.canvas.before:
            KColor(rgba=self.card_color)
            _bg = KRect(pos=status_card.pos, size=status_card.size)
            KColor(rgba=(self.muted_color[0], self.muted_color[1],
                         self.muted_color[2], 0.10))
            _div = KRect(pos=status_card.pos, size=(status_card.width, dp(1)))
        status_card.bind(
            pos=lambda w, v: (
                setattr(_bg, 'pos', v),
                setattr(_div, 'pos', v),
            ),
            size=lambda w, v: (
                setattr(_bg, 'size', v),
                setattr(_div, 'size', (v[0], dp(1))),
            ),
        )

        status_lbl = Label(
            text=self.status_text or self.phase_text,
            font_name='Nunito', font_size='14sp',
            color=self.text_color,
            halign='left', valign='middle',
            size_hint_y=None, height=dp(22),
        )
        status_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self.bind(
            status_text=lambda _, v: setattr(status_lbl, 'text', v or self.phase_text),
            phase_text=lambda _, v: (
                setattr(status_lbl, 'text', self.status_text or v)
                if not self.status_text else None
            ),
        )
        status_card.add_widget(status_lbl)

        # 5-segment progress bar
        bar = GridLayout(cols=5, size_hint_y=None, height=dp(8), spacing=dp(6))
        for n in range(1, 6):
            seg = Widget()

            def _draw(w, *_, seg_n=n):
                w.canvas.clear()
                with w.canvas:
                    c = self.brand_color if self.progress >= seg_n else (0.25, 0.25, 0.25, 0.5)
                    KColor(rgba=c)
                    KRR(pos=w.pos, size=w.size, radius=[dp(4)])

            seg.bind(pos=_draw, size=_draw)
            self.bind(progress=lambda _, v, w=seg, sn=n: _draw(w))
            _draw(seg)
            bar.add_widget(seg)

        status_card.add_widget(bar)
        parent.add_widget(status_card)

        # ── Map card ───────────────────────────────────────────────
        try:
            from kivy.garden.mapview import MapView, MapMarker, MapSource

            mv = MapView(
                size_hint_y=1,
                lat=self.marker_lat or 40.440624,
                lon=self.marker_lon or -79.995888,
                zoom=15,
                map_source=MapSource(
                    url='https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png',
                    attribution='',
                    cache_key='cartodb_dark',
                    min_zoom=12,
                    max_zoom=17,
                ),
            )

            courier_pin = MapMarker(
                lat=self.marker_lat, lon=self.marker_lon,
                source='screens/UberEats/resized_marker.png',
            )
            store_pin = MapMarker(
                lat=self.store_lat, lon=self.store_lon,
                source='screens/UberEats/restaurant.png',
            )
            home_pin = MapMarker(
                lat=self.home_lat, lon=self.home_lon,
                source='screens/UberEats/home.png',
            )
            mv.add_widget(courier_pin)
            mv.add_widget(store_pin)
            mv.add_widget(home_pin)

            # Keep pins in sync as coordinates update
            self.bind(marker_lat=lambda _, v: setattr(courier_pin, 'lat', v))
            self.bind(marker_lon=lambda _, v: setattr(courier_pin, 'lon', v))
            self.bind(store_lat=lambda _, v: setattr(store_pin, 'lat', v))
            self.bind(store_lon=lambda _, v: setattr(store_pin, 'lon', v))
            self.bind(home_lat=lambda _, v: setattr(home_pin, 'lat', v))
            self.bind(home_lon=lambda _, v: setattr(home_pin, 'lon', v))

            self._mapview = mv
            parent.add_widget(mv)

        except Exception as e:
            PIHOME_LOGGER.warn("UberEats: MapView unavailable: {}".format(e))
            fallback = Label(
                text='Map unavailable',
                font_name='Nunito', font_size='13sp',
                color=(self.muted_color[0], self.muted_color[1],
                       self.muted_color[2], 0.5),
                size_hint_y=1,
                halign='center', valign='middle',
            )
            parent.add_widget(fallback)