"""Nanoleaf REST API client for PiHome.

Communicates with Nanoleaf controllers over the local network using the
OpenAPI on port 16021.  All methods are blocking and intended to be called
from background threads — never from the Kivy main thread.
"""

import colorsys
import json
import urllib.error
import urllib.request

from util.phlog import PIHOME_LOGGER

_PORT = 16021
_TIMEOUT = 5


class NanoleafAPI:
    """Thread-safe Nanoleaf REST API client for a single controller."""

    def __init__(self, ip, token=""):
        self.ip = ip
        self.token = token

    @property
    def _base(self):
        return f"http://{self.ip}:{_PORT}/api/v1"

    def _url(self, path=""):
        return f"{self._base}/{self.token}{path}"

    def _request(self, path, method="GET", data=None):
        url = self._url(path)
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method=method)
        if body:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            PIHOME_LOGGER.error(f"Nanoleaf API HTTP {e.code}: {e.reason} — {url}")
            raise
        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf API error: {e} — {url}")
            raise

    # ── Pairing ───────────────────────────────────────────────────────────────

    def pair(self):
        """Pair with the controller.

        The user must hold the power button on the Nanoleaf for 5-7 seconds
        before calling this.  Returns the auth token string on success.
        """
        url = f"{self._base}/new"
        req = urllib.request.Request(url, data=b"", method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            result = json.loads(resp.read())
            return result.get("auth_token", "")

    # ── State ─────────────────────────────────────────────────────────────────

    def get_state(self):
        """Get full device state (power, brightness, hue, sat, effects, layout)."""
        return self._request("/")

    def get_power(self):
        state = self._request("/state/on")
        return state.get("value", False)

    def set_power(self, on):
        self._request("/state", method="PUT", data={"on": {"value": on}})

    def get_brightness(self):
        state = self._request("/state/brightness")
        return state.get("value", 100)

    def set_brightness(self, value):
        value = max(0, min(100, int(value)))
        self._request("/state", method="PUT", data={
            "brightness": {"value": value, "duration": 1}
        })

    # ── Layout ────────────────────────────────────────────────────────────────

    def get_layout(self):
        """Get panel layout data with positions and orientations."""
        return self._request("/panelLayout/layout")

    # ── Effects ───────────────────────────────────────────────────────────────

    def get_effects_list(self):
        """Get list of available effect names."""
        return self._request("/effects/effectsList")

    def get_current_effect(self):
        return self._request("/effects/select")

    def set_effect(self, name):
        self._request("/effects", method="PUT", data={"select": name})

    # ── Per-panel colors ──────────────────────────────────────────────────────

    def set_panel_color(self, panel_id, r, g, b, transition=1):
        """Set a single panel to an RGB color (0-255).

        ``transition`` is in 100 ms increments (1 = 100 ms).
        """
        self.set_panel_colors({panel_id: (r, g, b)}, transition)

    def set_panel_colors(self, panel_colors, transition=1):
        """Set multiple panels.  ``panel_colors``: ``{panel_id: (r, g, b)}``."""
        n = len(panel_colors)
        parts = [str(n)]
        for pid, (r, g, b) in panel_colors.items():
            parts.append(f"{pid} 1 {int(r)} {int(g)} {int(b)} 0 {transition}")
        anim_data = " ".join(parts)
        self._request("/effects", method="PUT", data={
            "write": {
                "command": "display",
                "animType": "static",
                "animData": anim_data,
                "loop": False,
                "palette": [],
            }
        })

    def set_all_color(self, r, g, b):
        """Set every panel to one color via global HSV state."""
        r_f, g_f, b_f = r / 255.0, g / 255.0, b / 255.0
        h, s, v = colorsys.rgb_to_hsv(r_f, g_f, b_f)
        data = {
            "hue": {"value": int(h * 360)},
            "sat": {"value": int(s * 100)},
            "brightness": {"value": max(1, int(v * 100))},
        }
        self._request("/state", method="PUT", data=data)

    # ── Panel color readback ──────────────────────────────────────────────────

    def get_panel_colors(self):
        """Try to read per-panel RGB colours from the current effect.

        Uses the ``write/request`` command to fetch the active animation's
        ``animData`` and parses per-panel colours from it.

        Returns ``{panel_id: (r, g, b)}`` or empty dict on failure.
        """
        try:
            fx_name = self._request("/effects/select")
            PIHOME_LOGGER.info(f"Nanoleaf API: effects/select returned: {fx_name!r} (type={type(fx_name).__name__})")
            if not fx_name or not isinstance(fx_name, str):
                return {}
            result = self._request("/effects", method="PUT", data={
                "write": {"command": "request", "animName": fx_name}
            })
            PIHOME_LOGGER.info(f"Nanoleaf API: write/request returned type={type(result).__name__}, keys={list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            if isinstance(result, dict):
                colors = self.parse_panel_colors_from_effect(result)
                PIHOME_LOGGER.info(f"Nanoleaf API: parsed {len(colors)} panel colors")
                return colors
        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf API: get_panel_colors error: {e}")
        return {}

    @staticmethod
    def parse_panel_colors_from_effect(effect_data):
        """Extract per-panel RGB dict from an effect's animData string.

        Returns ``{panel_id: (r, g, b)}`` or empty dict if unparseable.
        """
        try:
            anim = effect_data.get("animData", "")
            if not anim:
                return {}
            tokens = anim.split()
            idx = 0
            n_panels = int(tokens[idx]); idx += 1
            colors = {}
            for _ in range(n_panels):
                pid = int(tokens[idx]); idx += 1
                n_frames = int(tokens[idx]); idx += 1
                r = int(tokens[idx]); idx += 1
                g = int(tokens[idx]); idx += 1
                b = int(tokens[idx]); idx += 1
                idx += 1  # W
                idx += 1  # T
                colors[pid] = (r, g, b)
            return colors
        except Exception:
            return {}
