"""Wire-protocol helpers for the BluetoothConnect screen.

Deliberately free of Kivy, bleak and PiHome imports so the parsing logic can be
exercised headlessly -- see screens/BluetoothConnect/tests/test_protocol.py.

Devices talk to PiHome in newline-terminated UTF-8 over a BLE notify
characteristic. A notification carries at most (ATT_MTU - 3) bytes, and
ArduinoBLE's default MTU of 23 leaves only 20 usable, so a logical line often
arrives as several fragments and several short lines can share one fragment.
LineAssembler turns that byte stream back into whole lines.
"""

import copy

# ── The PiHome GATT contract ────────────────────────────────────────────────
# These are the defaults; each is overridable in Settings so a user can run an
# isolated pair of UUIDs. Lowercase, because bleak normalizes UUIDs that way.
DEFAULT_SERVICE_UUID = "87e85cbe-0094-417b-963b-aa888c375c36"
DEFAULT_TX_UUID = "eb96a621-c93b-4cca-b6c3-d79215350f65"   # device -> PiHome, notify
DEFAULT_RX_UUID = "6f7bf96c-3b16-4032-af4d-2fb9631cfdd1"   # PiHome -> device, write
DEFAULT_INFO_UUID = "5e29bcac-6f3f-4971-8dc5-65aa536e1792"  # friendly name, read

# A single notification payload at the guaranteed-minimum MTU. Outbound writes
# are chunked to this so they survive a device that never negotiates upward.
MAX_WRITE_CHUNK = 20

# A device that never sends a newline must not grow our buffer forever.
MAX_LINE = 512

# Reply a device must send after PiHome writes "AUTH <key>" before its commands
# are accepted. Compared case-insensitively.
AUTH_OK = "auth ok"


class LineAssembler:
    """Reassembles BLE notification fragments into complete lines.

    ``feed()`` returns the lines that completed with this fragment (often none).
    ``flush()`` exists for the idle-timeout path: a very common first-sketch
    mistake is forgetting the trailing "\\n", and flushing a quiet buffer makes
    that just work instead of silently dropping every command.
    """

    def __init__(self, max_line=MAX_LINE):
        self._buf = bytearray()
        self._max = max_line
        self.overflows = 0

    def feed(self, data):
        if not data:
            return []
        self._buf.extend(bytes(data))

        lines = []
        while True:
            idx = self._buf.find(b"\n")
            if idx < 0:
                break
            chunk = bytes(self._buf[:idx])
            del self._buf[: idx + 1]
            text = _clean(chunk)
            if text:
                lines.append(text)

        if len(self._buf) > self._max:
            self.overflows += 1
            self._buf.clear()
        return lines

    def flush(self):
        """Return whatever is buffered as a line and clear it. May return None."""
        if not self._buf:
            return None
        text = _clean(bytes(self._buf))
        self._buf.clear()
        return text or None

    @property
    def pending(self):
        return len(self._buf)

    def reset(self):
        self._buf.clear()


def _clean(raw):
    return raw.decode("utf-8", "replace").replace("\r", "").strip()


def parse_command(line):
    """Split a line into (command, value).

    'button_a'  -> ('button_a', None)
    'dial:12'   -> ('dial', '12')
    'dial=12'   -> ('dial', '12')

    The command is lowercased and stripped so a sketch's casing does not have to
    match the binding exactly. The value is passed through verbatim.
    """
    line = (line or "").strip()
    if not line:
        return "", None

    cut = -1
    for sep in (":", "="):
        idx = line.find(sep)
        if idx > 0 and (cut < 0 or idx < cut):
            cut = idx

    if cut < 0:
        return line.lower(), None

    command = line[:cut].strip().lower()
    value = line[cut + 1 :].strip()
    return command, (value or None)


def substitute(event, value):
    """Deep-copy ``event`` and replace every "$1" with ``value``.

    Same convention as ShellEvent.replace_vars (events/shellevent.py), so a
    binding can forward the device's value into the action it fires, e.g.
    binding 'dial' to {"type": "brightness", "level": "$1"}.

    Thin wrapper over the shared rule-store substitution, which handles both this
    positional form and named ``$name`` keys.
    """
    from util.rulestore import substitute as _substitute

    if value is None:
        return copy.deepcopy(event)
    return _substitute(event, {"1": value})


def normalize_uuid(value, fallback):
    """Accept a user-supplied 128-bit UUID, falling back when it is blank or junk.

    Tolerates the braces/uppercase forms people paste out of Arduino sketches.
    """
    text = (value or "").strip().strip("{}").lower()
    if not text:
        return fallback
    parts = text.split("-")
    if len(parts) != 5 or [len(p) for p in parts] != [8, 4, 4, 4, 12]:
        return fallback
    if any(c not in "0123456789abcdef-" for c in text):
        return fallback
    return text


def chunk(text, size=MAX_WRITE_CHUNK):
    """Split an outbound string into MTU-safe byte chunks (newline included)."""
    raw = text.encode("utf-8")
    if not raw.endswith(b"\n"):
        raw += b"\n"
    return [raw[i : i + size] for i in range(0, len(raw), size)]
