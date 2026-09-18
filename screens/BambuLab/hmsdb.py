"""hmsdb — human-readable text for BambuLab HMS and print-error codes.

The printer reports faults only as numeric codes (``0700_2000_0002_0001``),
which are useless on a wall-mounted display without a phone in hand. Bambu
publishes the matching English descriptions as a single public JSON document:

    https://e.bambulab.com/query.php?lang=en

This module turns that document into two flat ``code -> sentence`` maps and
resolves codes against them.

Data sources, in priority order
-------------------------------
  1. ``cache/bambu_hms_en.json``  — refreshed in the background, used when its
                                     ``ver`` is at least the bundled one.
  2. ``screens/BambuLab/hms_en.json`` — the snapshot committed with the screen,
                                     so descriptions work offline on first boot.

Both files use this module's own compact shape (``{"ver", "hms", "error"}``),
not the upstream envelope; :func:`_transform` converts one to the other.

Kivy-free by design — see ``tests/test_core.py``.
"""

import json
import os
import threading
import time
import urllib.request

_URL = "https://e.bambulab.com/query.php?lang=en"

# The endpoint 403s a request without a browser-ish User-Agent.
_USER_AGENT = "Mozilla/5.0 (compatible; PiHome/1.0)"

_BUNDLED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hms_en.json")
_CACHE_PATH = "cache/bambu_hms_en.json"

# Re-fetch at most this often. The list changes only with firmware releases.
_REFRESH_INTERVAL = 7 * 24 * 3600

_FETCH_TIMEOUT = 20

# Nunito covers basic Latin only, so anything outside ASCII renders as a tofu
# square. Upstream text contains degree signs, curly quotes and (in a handful of
# entries) CJK punctuation — fold those to ASCII rather than dropping them.
_ASCII_FOLD = {
    "°": " deg",
    "“": '"', "”": '"',
    "‘": "'", "’": "'",
    "–": "-", "—": "-",
    "…": "...",
    "。": ".", "，": ",", "：": ":", "；": ";",
    "（": "(", "）": ")", " ": " ",
}


def _to_ascii(text):
    """Fold a description to ASCII so Nunito can render every character."""
    out = []
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
        else:
            out.append(_ASCII_FOLD.get(ch, ""))
    return " ".join("".join(out).split())


def _transform(payload):
    """Convert the upstream envelope into this module's compact shape."""
    data = (payload or {}).get("data") or {}

    def table(section):
        out = {}
        for entry in (data.get(section) or {}).get("en") or []:
            code = str(entry.get("ecode", "")).strip().upper()
            intro = _to_ascii(str(entry.get("intro", "")).strip())
            if code and intro:
                out[code] = intro
        return out

    return {
        "ver": payload.get("ver"),
        "hms": table("device_hms"),
        "error": table("device_error"),
    }


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("hms"), dict):
        return None
    return doc


def _version(doc):
    try:
        return int(doc.get("ver") or 0)
    except (TypeError, ValueError):
        return 0


class HmsDatabase:
    """Code -> description lookups, loaded lazily and refreshed in the background."""

    def __init__(self, bundled_path=_BUNDLED_PATH, cache_path=_CACHE_PATH):
        self._bundled_path = bundled_path
        self._cache_path = cache_path
        self._lock = threading.Lock()
        self._doc = None
        self._refresh_thread = None

    # ── Loading ──

    def _load(self):
        """Return the active document, preferring the cache when it isn't older."""
        with self._lock:
            if self._doc is not None:
                return self._doc
            bundled = _read(self._bundled_path) or {"ver": 0, "hms": {}, "error": {}}
            cached = _read(self._cache_path)
            if cached is not None and _version(cached) >= _version(bundled):
                self._doc = cached
            else:
                self._doc = bundled
            return self._doc

    @property
    def version(self):
        return _version(self._load())

    @property
    def count(self):
        doc = self._load()
        return len(doc.get("hms", {})) + len(doc.get("error", {}))

    # ── Lookups ──

    def describe_hms(self, code):
        """Describe a 16-hex HMS code. Underscores and case are ignored."""
        key = str(code or "").replace("_", "").strip().upper()
        return self._load().get("hms", {}).get(key, "")

    def describe_error(self, code):
        """Describe a print-error code, given as an int or an 8-hex string."""
        if isinstance(code, int):
            key = "{:08X}".format(code & 0xFFFFFFFF)
        else:
            key = str(code or "").replace("_", "").replace("0x", "").strip().upper()
        return self._load().get("error", {}).get(key, "")

    # ── Background refresh ──

    def _cache_is_fresh(self):
        try:
            return (time.time() - os.path.getmtime(self._cache_path)) < _REFRESH_INTERVAL
        except OSError:
            return False

    def refresh_async(self, force=False):
        """Fetch a newer dictionary in a daemon thread. Safe to call repeatedly."""
        if not force and self._cache_is_fresh():
            return False
        with self._lock:
            if self._refresh_thread is not None and self._refresh_thread.is_alive():
                return False
            self._refresh_thread = threading.Thread(
                target=self._refresh, daemon=True, name="bambulab-hmsdb"
            )
            self._refresh_thread.start()
        return True

    def _refresh(self):
        try:
            request = urllib.request.Request(_URL, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            doc = _transform(payload)
            if not doc["hms"]:
                raise ValueError("no HMS entries in response")

            os.makedirs(os.path.dirname(self._cache_path) or ".", exist_ok=True)
            tmp = self._cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            os.replace(tmp, self._cache_path)

            with self._lock:
                # Only adopt it in-process if it isn't older than what we have.
                if self._doc is None or _version(doc) >= _version(self._doc):
                    self._doc = doc
        except Exception as exc:  # network, parse, disk — all non-fatal
            _log_warning("BambuLab: HMS description refresh failed: %s" % exc)


def _log_warning(message):
    """Log through PiHome when available; stay importable in headless tests."""
    try:
        from util.phlog import PIHOME_LOGGER
        PIHOME_LOGGER.warning(message)
    except Exception:
        pass


HMS_DB = HmsDatabase()
