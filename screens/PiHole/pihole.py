import os
import json as _json
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.network.urlrequest import UrlRequest
from kivy.properties import StringProperty, ColorProperty, BooleanProperty
from kivy.clock import Clock
from interface.pihomescreen import PiHomeScreen
from networking.poller import POLLER
from theme.theme import Theme
from util.configuration import CONFIG
from util.const import CDN_ASSET
from util.helpers import toast
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/PiHole/pihole.kv")


class PiHoleScreen(PiHomeScreen):
    """
    PiHole Dashboard — live stats, enable/disable toggle.
    """

    # ── Theme colours ────────────────────────────────────────────────
    bg_color      = ColorProperty([0, 0, 0, 1])
    header_color  = ColorProperty([0, 0, 0, 1])
    card_color    = ColorProperty([0, 0, 0, 0.4])
    text_color    = ColorProperty([1, 1, 1, 1])
    muted_color   = ColorProperty([0.5, 0.5, 0.5, 1])
    accent_color  = ColorProperty([0.36, 0.67, 1.0, 1.0])
    status_color  = ColorProperty([0.5, 0.5, 0.5, 1])

    # ── Data ───────────────────────────────────────────────────────
    domains_being_blocked = StringProperty("-")
    ads_blocked_today     = StringProperty("-")
    unique_clients        = StringProperty("-")
    status                = StringProperty("UNKNOWN")
    status_text           = StringProperty("UNKNOWN")
    blocking              = BooleanProperty(False)

    HOST             = "http://pi.hole"
    API_KEY          = ""
    UPDATE_FREQUENCY = 30
    is_visible       = False
    API_SID          = None
    _poller_key      = None
    _syncing         = False

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

        self.icon = CDN_ASSET.format("pihole.png")
        if CONFIG.get('pihole', 'enabled', False):
            self.HOST    = CONFIG.get('pihole', 'host', "http://pi.hole")
            self.API_KEY = CONFIG.get('pihole', 'api_key', "")

    # ── Auth ──────────────────────────────────────────────────────
    def _authenticate(self):
        """POST /api/auth with password, then start polling."""
        url = "{}/api/auth".format(self.HOST)
        body = _json.dumps({"password": self.API_KEY})
        UrlRequest(
            url=url,
            req_body=body,
            req_headers={'Content-Type': 'application/json'},
            on_success=lambda req, result: self._on_auth_success(result),
            on_failure=lambda req, result: (
                PIHOME_LOGGER.error("PiHole auth failed: {}".format(result)),
                self._start_polling()
            ),
            on_error=lambda req, err: (
                PIHOME_LOGGER.error("PiHole auth error: {}".format(err)),
                self._start_polling()
            )
        )

    def _on_auth_success(self, result):
        try:
            session = result.get('session', {})
            if session.get('valid'):
                self.API_SID = session.get('sid')
                PIHOME_LOGGER.info("PiHole auth OK, SID: {}".format(self.API_SID))
            else:
                PIHOME_LOGGER.warn("PiHole auth response: {}".format(result))
        except Exception as e:
            PIHOME_LOGGER.error("PiHole auth parse error: {}".format(e))
        self._start_polling()

    # ── Poller lifecycle ──────────────────────────────────────────
    def _start_polling(self):
        """Register stats poller and fetch current blocking status."""
        if self._poller_key is None:
            self._poller_key = POLLER.register_api(
                self.get_pihole_uri(), self.UPDATE_FREQUENCY,
                lambda data: self.update(data)
            )
            PIHOME_LOGGER.info("PiHole poller registered: {}".format(self.get_pihole_uri()))
        self._fetch_blocking_status()

    def _stop_polling(self):
        """Unregister the stats poller."""
        if self._poller_key is not None:
            POLLER.unregister_api(self._poller_key)
            self._poller_key = None
            PIHOME_LOGGER.info("PiHole poller unregistered")

    def get_pihole_uri(self):
        uri = "{}/api/stats/summary".format(self.HOST)
        if self.API_SID:
            uri += "?sid={}".format(self.API_SID)
        return uri

    # ── Blocking status ───────────────────────────────────────────
    def _fetch_blocking_status(self):
        """GET /api/dns/blocking to read the current enable/disable state."""
        url = self._with_sid("{}/api/dns/blocking".format(self.HOST))
        PIHOME_LOGGER.info("PiHole fetching blocking status: {}".format(url))
        UrlRequest(
            url=url,
            req_headers={'User-Agent': 'Mozilla/5.0'},
            on_success=lambda req, result: self._apply_blocking_status(result),
            on_failure=lambda req, result: PIHOME_LOGGER.error(
                "PiHole blocking status HTTP {}: {}".format(req.resp_status, result)),
            on_error=lambda req, err: PIHOME_LOGGER.error(
                "PiHole blocking status error: {}".format(err)),
        )

    def _apply_blocking_status(self, result):
        """Update blocking/status from a /api/dns/blocking response.
        The 'blocking' field is a STRING enum: 'enabled'/'disabled'/'failed'/'unknown'.
        """
        PIHOME_LOGGER.info("PiHole blocking result: {}".format(result))
        val = result.get('blocking', None)
        if val is None:
            return
        # v6 returns a string enum; guard against any future boolean form too
        if isinstance(val, str):
            active = (val.lower() == 'enabled')
        else:
            active = bool(val)
        self._syncing = True
        try:
            self.blocking    = active
            self.status      = 'enabled' if active else 'disabled'
            self.status_text = 'ENABLED' if active else 'DISABLED'
            if 'pihole_switch' in self.ids:
                self.ids.pihole_switch.enabled = active
        finally:
            self._syncing = False

    def on_status(self, instance, value):
        theme = Theme()
        if value == 'enabled':
            self.status_color = theme.get_color(theme.TEXT_SUCCESS)
        elif value == 'disabled':
            self.status_color = theme.get_color(theme.TEXT_DANGER)
        else:
            self.status_color = theme.get_color(theme.TEXT_SECONDARY)

    def _with_sid(self, url):
        """Append ?sid= query parameter when we have a session."""
        if self.API_SID:
            sep = '&' if '?' in url else '?'
            return "{}{}sid={}".format(url, sep, self.API_SID)
        return url

    def toggle_pihole(self, active):
        """Called by the switch; ignored when _syncing (programmatic update)."""
        if self._syncing:
            return
        if not active:
            toast("PiHole disabled for 5 minutes!", "warn")
        url_str = self._with_sid("{}/api/dns/blocking".format(self.HOST))
        PIHOME_LOGGER.info("PiHole toggle → {} url={}".format(active, url_str))
        body = _json.dumps({"blocking": active, "timer": None if active else 300})
        UrlRequest(
            url=url_str,
            req_body=body,
            req_headers={'Content-Type': 'application/json'},
            on_success=lambda req, result: self._apply_blocking_status(result),
            on_failure=lambda req, result: (
                PIHOME_LOGGER.error("PiHole toggle HTTP {}: {}".format(req.resp_status, result)),
                self._fetch_blocking_status()
            ),
            on_error=lambda req, err: (
                PIHOME_LOGGER.error("PiHole toggle error: {}".format(err)),
                self._fetch_blocking_status()
            ),
        )

    def on_enter(self, *args):
        self.is_visible = True
        if CONFIG.get('pihole', 'enabled', False) and not self.is_hidden:
            if self.API_KEY and self.API_SID is None:
                self._authenticate()        # auth → _start_polling
            else:
                self._start_polling()       # already auth'd (or no password)
        return super().on_enter(*args)

    def on_exit(self, *args):
        self.is_visible = False
        self._stop_polling()
        return super().on_exit(*args)

    def on_config_update(self, config):
        """Reload PiHole credentials and restart the poller when settings change."""
        enabled  = config.get('pihole', 'enabled', False)
        new_host = config.get('pihole', 'host', 'http://pi.hole')
        new_key  = config.get('pihole', 'api_key', '')

        credentials_changed = (new_host != self.HOST or new_key != self.API_KEY)
        self.HOST    = new_host
        self.API_KEY = new_key

        if not enabled:
            self._stop_polling()
        elif credentials_changed:
            self.API_SID = None   # force re-auth with new credentials
            self._stop_polling()
            if self.is_visible:
                if new_key:
                    self._authenticate()
                else:
                    self._start_polling()

        super().on_config_update(config)

    def update(self, data):
        if not self.is_visible:
            return
        # ── v6 nested response ─────────────────────────────────────
        if 'gravity' in data:
            self.domains_being_blocked = str(
                data['gravity'].get('domains_being_blocked', '-'))
        elif 'domains_being_blocked' in data:   # v5 fallback
            self.domains_being_blocked = str(data['domains_being_blocked'])

        if 'queries' in data:
            self.ads_blocked_today = str(
                data['queries'].get('blocked', '-'))
        elif 'ads_blocked_today' in data:       # v5 fallback
            self.ads_blocked_today = str(data['ads_blocked_today'])

        if 'clients' in data:
            self.unique_clients = str(
                data['clients'].get('active', '-'))
        elif 'unique_clients' in data:          # v5 fallback
            self.unique_clients = str(data['unique_clients'])

        # blocking status — present in some responses; use dedicated endpoint otherwise
        if 'blocking' in data:
            self._apply_blocking_status(data)
        elif 'status' in data:   # v5 fallback
            val = data['status']
            self._syncing = True
            try:
                self.blocking    = (val == 'enabled')
                self.status      = val
                self.status_text = val.upper()
            finally:
                self._syncing = False
