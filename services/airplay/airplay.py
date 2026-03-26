"""AirPlay metadata service — reads shairport-sync's named pipe.

Parses track title, artist, album, and cover art from the metadata FIFO
and notifies registered listeners on the Kivy main thread.
"""

import base64
import hashlib
import os
import platform
import select
import threading
import time

from kivy.clock import Clock
from util.phlog import PIHOME_LOGGER

_PIPE_PATH = "/tmp/shairport-sync-metadata"

# Hex-encoded type/code → friendly key
_CODE_MAP = {
    ("core", "minm"): "title",
    ("core", "asar"): "artist",
    ("core", "asal"): "album",
    ("ssnc", "PICT"): "cover_art",
    ("ssnc", "pbeg"): "play_begin",
    ("ssnc", "pend"): "play_end",
    ("ssnc", "pfls"): "pause",
    ("ssnc", "prsm"): "resume",
}

def _hex_to_ascii(hex_str):
    """Convert an 8-char hex string to a 4-char ASCII string."""
    try:
        return bytes.fromhex(hex_str).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return hex_str


class AirPlay:
    """Singleton service that reads shairport-sync metadata from a named pipe."""

    def __init__(self):
        self.title = ""
        self.artist = ""
        self.album = ""
        self.cover_art_bytes = None
        self.is_playing = False

        self._listeners = []
        self._stop_event = threading.Event()
        self._cover_hash = None
        self._pend_time = None  # monotonic timestamp of last play_end

        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="airplay-metadata"
        )
        self._thread.start()

    # ── Listener API ──────────────────────────────────────────────────

    def register_listener(self, callback):
        """Register a callback(airplay_instance) invoked on the main thread."""
        if callback not in self._listeners:
            self._listeners.append(callback)
        # Immediately notify with current state
        Clock.schedule_once(lambda dt, cb=callback: cb(self), 0)

    def unregister_listener(self, callback):
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass

    def _notify(self):
        Clock.schedule_once(lambda dt: self._fire_listeners(), 0)

    def _fire_listeners(self):
        for cb in self._listeners:
            try:
                cb(self)
            except Exception as e:
                PIHOME_LOGGER.error("AirPlay: listener error: {}".format(e))

    # ── Background worker ─────────────────────────────────────────────

    def _worker(self):
        if platform.system() != "Linux":
            PIHOME_LOGGER.info("AirPlay: not on Linux, metadata pipe disabled")
            return

        while not self._stop_event.is_set():
            try:
                self._read_pipe()
            except Exception as e:
                PIHOME_LOGGER.error("AirPlay: pipe error: {}".format(e))
            # Wait before retrying (pipe disappeared, shairport-sync restarted, etc.)
            self._stop_event.wait(5)

    def _read_pipe(self):
        if not os.path.exists(_PIPE_PATH):
            PIHOME_LOGGER.info("AirPlay: pipe not found at {}, waiting...".format(_PIPE_PATH))
            self._stop_event.wait(30)
            return

        PIHOME_LOGGER.info("AirPlay: opening pipe at {}".format(_PIPE_PATH))

        # Open non-blocking so we don't hang if no writer
        fd = os.open(_PIPE_PATH, os.O_RDONLY | os.O_NONBLOCK)
        try:
            buf = ""
            while not self._stop_event.is_set():
                # Check for play_end timeout
                self._check_pend_timeout()

                # Wait for data with a 1-second timeout
                ready, _, _ = select.select([fd], [], [], 1.0)
                if not ready:
                    continue

                chunk = os.read(fd, 65536)
                if not chunk:
                    # No writer has the pipe open — wait and retry select
                    # (on FIFOs with O_NONBLOCK, empty read means no writer,
                    # not necessarily permanent EOF)
                    self._stop_event.wait(1)
                    continue

                buf += chunk.decode("utf-8", errors="replace")

                # Process complete items
                while "</item>" in buf:
                    end_idx = buf.index("</item>") + len("</item>")
                    item_str = buf[:end_idx]
                    buf = buf[end_idx:]
                    self._parse_item(item_str)
        finally:
            PIHOME_LOGGER.info("AirPlay: pipe closed")
            os.close(fd)

    def _check_pend_timeout(self):
        """If play_end was received >10s ago with no play_begin, mark stopped."""
        if self._pend_time is not None:
            if time.monotonic() - self._pend_time > 10:
                self._pend_time = None
                if self.is_playing:
                    self.is_playing = False
                    self._notify()

    # ── Metadata parsing ──────────────────────────────────────────────

    def _parse_item(self, item_str):
        """Parse a single <item>...</item> block from the pipe."""
        type_hex = self._extract_tag(item_str, "type")
        code_hex = self._extract_tag(item_str, "code")
        if not type_hex or not code_hex:
            return

        type_ascii = _hex_to_ascii(type_hex)
        code_ascii = _hex_to_ascii(code_hex)
        key = _CODE_MAP.get((type_ascii, code_ascii))

        PIHOME_LOGGER.info("AirPlay: item type={} code={} key={}".format(type_ascii, code_ascii, key))

        if key is None:
            return

        # Extract data payload (may be absent for signal-only items)
        data_b64 = self._extract_tag(item_str, "data")
        data_bytes = None
        if data_b64:
            try:
                data_bytes = base64.b64decode(data_b64)
            except Exception:
                data_bytes = None

        changed = False

        if key == "title":
            val = data_bytes.decode("utf-8", errors="replace") if data_bytes else ""
            if val != self.title:
                self.title = val
                changed = True

        elif key == "artist":
            val = data_bytes.decode("utf-8", errors="replace") if data_bytes else ""
            if val != self.artist:
                self.artist = val
                changed = True

        elif key == "album":
            val = data_bytes.decode("utf-8", errors="replace") if data_bytes else ""
            if val != self.album:
                self.album = val
                changed = True

        elif key == "cover_art":
            if data_bytes:
                new_hash = hashlib.md5(data_bytes).hexdigest()
                if new_hash != self._cover_hash:
                    self._cover_hash = new_hash
                    self.cover_art_bytes = data_bytes
                    changed = True
            else:
                if self.cover_art_bytes is not None:
                    self.cover_art_bytes = None
                    self._cover_hash = None
                    changed = True

        elif key == "play_begin" or key == "resume":
            self._pend_time = None
            if not self.is_playing:
                self.is_playing = True
                changed = True

        elif key == "play_end":
            self._pend_time = time.monotonic()
            # Don't mark stopped yet — wait for timeout
            return

        elif key == "pause":
            # Keep is_playing True for pause (card stays visible)
            pass

        if changed:
            self._notify()

    def _extract_tag(self, text, tag):
        """Extract content between <tag>...</tag> or <tag encoding="base64">...</tag>."""
        # Find opening tag (may have attributes)
        open_start = text.find("<{}>".format(tag))
        if open_start == -1:
            open_start = text.find("<{}".format(tag))
            if open_start == -1:
                return None
            # Find end of opening tag
            open_end = text.find(">", open_start)
            if open_end == -1:
                return None
            open_end += 1
        else:
            open_end = open_start + len("<{}>".format(tag))

        close_tag = "</{}>".format(tag)
        close_start = text.find(close_tag, open_end)
        if close_start == -1:
            return None

        return text[open_end:close_start].strip()


AIRPLAY = AirPlay()
