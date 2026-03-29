"""AirPlay metadata service — reads shairport-sync's named pipe.

Parses track title, artist, album, and cover art from the metadata FIFO
and notifies registered listeners on the Kivy main thread.
"""

import atexit
import base64
import hashlib
import json
import os
import platform
import select
import threading
import time
import uuid

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
    ("ssnc", "mdst"): "metadata_start",
    ("ssnc", "mden"): "metadata_end",
}

def _hex_to_ascii(hex_str):
    """Convert an 8-char hex string to a 4-char ASCII string."""
    try:
        return bytes.fromhex(hex_str).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return hex_str


class AirPlayReactListener:
    """A persistent AirPlay state-change listener that fires a PiHome event.
    Serialised to / from airplay_listeners.pihome as plain JSON."""

    def __init__(self, trigger, action, id=None):
        self.id      = id or str(uuid.uuid4())
        self.trigger = trigger  # "on_start" or "on_stop"
        self.action  = action   # dict — executed via PihomeEventFactory

    def to_dict(self):
        return {
            "id":      self.id,
            "trigger": self.trigger,
            "action":  self.action,
        }

    @staticmethod
    def from_dict(d):
        return AirPlayReactListener(
            trigger = d["trigger"],
            action  = d["action"],
            id      = d["id"],
        )


class AirPlay:
    """Singleton service that reads shairport-sync metadata from a named pipe."""

    REACT_LISTENERS_FILE = "airplay_listeners.pihome"

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

        self.react_listeners = []
        self._deserialize_react_listeners()
        atexit.register(self._serialize_react_listeners)

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

    # ── React Listener API ──────────────────────────────────────────────

    def add_react_listener(self, listener: AirPlayReactListener):
        """Register a persistent react listener and persist to disk."""
        self.react_listeners.append(listener)
        self._serialize_react_listeners()
        PIHOME_LOGGER.info(
            f"AirPlayReactListener added: {listener.id} "
            f"(trigger={listener.trigger})"
        )
        return listener.id

    def remove_react_listener(self, listener_id: str) -> bool:
        """Remove a react listener by ID and persist the change."""
        before = len(self.react_listeners)
        self.react_listeners = [
            l for l in self.react_listeners if l.id != listener_id
        ]
        removed = len(self.react_listeners) < before
        if removed:
            self._serialize_react_listeners()
            PIHOME_LOGGER.info(f"AirPlayReactListener removed: {listener_id}")
        else:
            PIHOME_LOGGER.warn(f"AirPlayReactListener not found for removal: {listener_id}")
        return removed

    def _fire_react_listeners(self, trigger):
        """Fire all react listeners matching the given trigger."""
        from events.pihomeevent import PihomeEventFactory

        for listener in list(self.react_listeners):
            if listener.trigger == trigger:
                try:
                    PIHOME_LOGGER.info(
                        f"AirPlayReactListener {listener.id}: firing for {trigger}"
                    )
                    Clock.schedule_once(
                        lambda _dt, a=listener.action:
                            PihomeEventFactory.create_event_from_dict(a).execute(),
                        0
                    )
                except Exception as e:
                    PIHOME_LOGGER.error(
                        f"AirPlayReactListener {listener.id}: failed to fire: {e}"
                    )

    def _serialize_react_listeners(self):
        data = [l.to_dict() for l in self.react_listeners]
        try:
            with open(self.REACT_LISTENERS_FILE, "w") as f:
                json.dump(data, f, indent=2)
            PIHOME_LOGGER.info(
                f"Serialized {len(data)} AirPlay react listener(s) to "
                f"{self.REACT_LISTENERS_FILE}"
            )
        except Exception as e:
            PIHOME_LOGGER.error(f"Failed to serialize AirPlay react listeners: {e}")

    def _deserialize_react_listeners(self):
        if not os.path.exists(self.REACT_LISTENERS_FILE):
            return
        try:
            with open(self.REACT_LISTENERS_FILE, "r") as f:
                data = json.load(f)
            self.react_listeners = [AirPlayReactListener.from_dict(d) for d in data]
            PIHOME_LOGGER.info(
                f"Loaded {len(self.react_listeners)} AirPlay react listener(s) "
                f"from {self.REACT_LISTENERS_FILE}"
            )
        except Exception as e:
            PIHOME_LOGGER.error(f"Failed to deserialize AirPlay react listeners: {e}")

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
            # Pipe closed — shairport-sync likely stopped
            if self.is_playing:
                PIHOME_LOGGER.info("AirPlay: playback stopped (pipe disconnected)")
                self.is_playing = False
                self._pend_time = None
                self._fire_react_listeners("on_stop")
                self._notify()

    def _check_pend_timeout(self):
        """Mark stopped if play_end received >10s ago with no new play_begin."""
        if self._pend_time is not None:
            if time.monotonic() - self._pend_time > 10:
                self._pend_time = None
                if self.is_playing:
                    PIHOME_LOGGER.info("AirPlay: playback stopped (play_end timeout)")
                    self.is_playing = False
                    self._fire_react_listeners("on_stop")
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

        elif key in ("play_begin", "resume", "metadata_start"):
            self._pend_time = None
            if not self.is_playing:
                PIHOME_LOGGER.info("AirPlay: playback started (via {})".format(key))
                self.is_playing = True
                self._fire_react_listeners("on_start")
                changed = True

        elif key == "play_end":
            self._pend_time = time.monotonic()
            # Don't mark stopped yet — wait for timeout
            return

        elif key == "metadata_end":
            # End of a metadata batch, not end of playback — ignore
            pass

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
