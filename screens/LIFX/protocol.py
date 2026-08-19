"""LIFX LAN protocol (v2) - framing, payloads and colour maths.

Stdlib only, no Kivy, no network.  Everything here is a pure function over
bytes so it can be unit tested with the system ``python3``::

    python3 screens/LIFX/tests/test_protocol.py

Wire format (little-endian throughout).  The header is always 36 bytes:

    Frame           8   size u16 | protocol/flags u16 | source u32
    Frame Address  16   target u64 | reserved 6B | flags u8 | sequence u8
    Protocol Hdr   12   reserved u64 | type u16 | reserved u16

Two details in the protocol/flags word bite everybody at least once:
``addressable`` (bit 12) must be set on *every* frame including unicast, and
in the frame-address flag byte ``res_required`` is bit 0 while
``ack_required`` is bit 1 - reversing them means SetColor never acks and the
retry loop fires on every drag frame.
"""

import colorsys
import math
import struct

# ── Wire constants ────────────────────────────────────────────────────────

LIFX_PORT = 56700
PROTOCOL = 1024
HEADER_SIZE = 36

_ADDRESSABLE = 1 << 12
_TAGGED = 1 << 13

_RES_REQUIRED = 0x01   # frame-address flag byte, bit 0
_ACK_REQUIRED = 0x02   # frame-address flag byte, bit 1

# Message types
GET_SERVICE = 2
STATE_SERVICE = 3
GET_HOST_FIRMWARE = 14
GET_VERSION = 32
STATE_VERSION = 33
ACKNOWLEDGEMENT = 45
GET_LOCATION = 48
STATE_LOCATION = 50
GET_GROUP = 51
STATE_GROUP = 53
LIGHT_GET = 101
LIGHT_SET_COLOR = 102
LIGHT_STATE = 107
LIGHT_GET_POWER = 116
LIGHT_SET_POWER = 117
LIGHT_STATE_POWER = 118

# HSBK ranges
U16 = 65535
KELVIN_MIN = 1500
KELVIN_MAX = 9000

_HEADER_FMT = "<HHI8s6sBBQHH"

# Payload formats
_FMT_STATE_SERVICE = "<BI"
_FMT_LIGHT_STATE = "<HHHHhH32sQ"      # 52 bytes
_FMT_SET_COLOR = "<BHHHHI"            # 13 bytes
_FMT_SET_POWER = "<HI"                # 6 bytes
_FMT_STATE_POWER = "<H"
_FMT_STATE_GROUP = "<16s32sQ"         # 56 bytes
_FMT_STATE_VERSION = "<II4x"          # 12 bytes


class ProtocolError(Exception):
    """A datagram could not be parsed as a LIFX frame or payload."""


class Frame(object):
    """A decoded LIFX message.  ``serial`` is None for a tagged (broadcast) frame."""

    __slots__ = ("size", "tagged", "source", "serial", "ack_required",
                 "res_required", "sequence", "msg_type", "payload")

    def __init__(self, size, tagged, source, serial, ack_required,
                 res_required, sequence, msg_type, payload):
        self.size = size
        self.tagged = tagged
        self.source = source
        self.serial = serial
        self.ack_required = ack_required
        self.res_required = res_required
        self.sequence = sequence
        self.msg_type = msg_type
        self.payload = payload

    def __repr__(self):
        return ("Frame(type={}, serial={}, seq={}, source={}, payload={}B)"
                .format(self.msg_type, self.serial, self.sequence,
                        self.source, len(self.payload)))

    def __eq__(self, other):
        if not isinstance(other, Frame):
            return NotImplemented
        return all(getattr(self, s) == getattr(other, s) for s in self.__slots__)


# ── Serial / target helpers ───────────────────────────────────────────────

def normalize_serial(text):
    """Accept 'd0:73:d5:12:34:56', 'D073D5123456', 'd073d5-123456' -> 'd073d5123456'.

    Returns None if *text* is not 12 hex digits once separators are stripped.
    """
    if not text:
        return None
    cleaned = "".join(c for c in str(text).lower() if c in "0123456789abcdef")
    if len(cleaned) != 12:
        return None
    return cleaned


def serial_to_target(serial):
    """'d073d5123456' -> 8 bytes: the 6 MAC bytes in order, then two zero bytes."""
    clean = normalize_serial(serial)
    if clean is None:
        raise ProtocolError("Invalid LIFX serial: {!r}".format(serial))
    return bytes.fromhex(clean) + b"\x00\x00"


def target_to_serial(raw):
    """Inverse of serial_to_target.  Returns None for the all-zero (broadcast) target."""
    if len(raw) < 6:
        raise ProtocolError("Target field too short: {} bytes".format(len(raw)))
    mac = raw[:6]
    if mac == b"\x00\x00\x00\x00\x00\x00":
        return None
    return mac.hex()


# ── Framing ───────────────────────────────────────────────────────────────

def pack(msg_type, payload=b"", source=0, sequence=0, serial=None,
         ack_required=False, res_required=False, tagged=None):
    """Build a complete LIFX datagram.

    *tagged* defaults to True when no *serial* is given (a broadcast), False
    otherwise.  ``addressable`` is always set and ``origin`` always zero, so
    the protocol word is 0x3400 broadcast / 0x1400 unicast.
    """
    payload = payload or b""
    if tagged is None:
        tagged = serial is None

    proto = PROTOCOL | _ADDRESSABLE
    if tagged:
        proto |= _TAGGED

    target = serial_to_target(serial) if serial else b"\x00" * 8

    flags = 0
    if res_required:
        flags |= _RES_REQUIRED
    if ack_required:
        flags |= _ACK_REQUIRED

    size = HEADER_SIZE + len(payload)
    header = struct.pack(
        _HEADER_FMT,
        size,                   # frame: size
        proto,                  # frame: protocol | addressable | tagged | origin
        source & 0xFFFFFFFF,    # frame: source
        target,                 # frame address: target
        b"\x00" * 6,            # frame address: reserved
        flags,                  # frame address: res/ack flags
        sequence & 0xFF,        # frame address: sequence
        0,                      # protocol header: reserved
        msg_type,               # protocol header: type
        0,                      # protocol header: reserved
    )
    return header + payload


def unpack(data):
    """Decode a datagram into a :class:`Frame`.  Raises ProtocolError on garbage."""
    if len(data) < HEADER_SIZE:
        raise ProtocolError(
            "Frame too short: {} bytes (need {})".format(len(data), HEADER_SIZE))

    (size, proto, source, target, _reserved, flags, sequence,
     _reserved2, msg_type, _reserved3) = struct.unpack(
        _HEADER_FMT, data[:HEADER_SIZE])

    if (proto & 0x0FFF) != PROTOCOL:
        raise ProtocolError("Not a LIFX frame: protocol={}".format(proto & 0x0FFF))

    # `size` counts header + payload.  Trust the datagram length when the two
    # disagree - a truncated UDP read is more likely than a lying bulb.
    payload = data[HEADER_SIZE:size] if size <= len(data) else data[HEADER_SIZE:]

    return Frame(
        size=size,
        tagged=bool(proto & _TAGGED),
        source=source,
        serial=target_to_serial(target),
        ack_required=bool(flags & _ACK_REQUIRED),
        res_required=bool(flags & _RES_REQUIRED),
        sequence=sequence,
        msg_type=msg_type,
        payload=payload,
    )


# ── Payload builders ──────────────────────────────────────────────────────

def payload_set_color(hue, saturation, brightness, kelvin, duration_ms=0):
    """Light::SetColor (102).  HSBK values are raw u16; kelvin is a real Kelvin value."""
    return struct.pack(
        _FMT_SET_COLOR,
        0,                                  # reserved
        int(hue) & U16,
        int(saturation) & U16,
        int(brightness) & U16,
        int(kelvin) & U16,
        max(0, int(duration_ms)) & 0xFFFFFFFF,
    )


def payload_set_power(on, duration_ms=0):
    """Light::SetPower (117).  Level is 0 or 65535."""
    level = U16 if on else 0
    return struct.pack(_FMT_SET_POWER, level, max(0, int(duration_ms)) & 0xFFFFFFFF)


# ── Payload parsers ───────────────────────────────────────────────────────

def _need(payload, size, what):
    if len(payload) < size:
        raise ProtocolError(
            "{} payload too short: {} bytes (need {})".format(what, len(payload), size))


def _label(raw):
    """Decode a fixed 32-byte label field.  Handles both NUL-padded and full-width."""
    return raw.split(b"\x00", 1)[0].decode("utf-8", "replace").strip()


def parse_state_service(payload):
    _need(payload, 5, "StateService")
    service, port = struct.unpack(_FMT_STATE_SERVICE, payload[:5])
    return {"service": service, "port": port}


def parse_light_state(payload):
    _need(payload, 52, "LightState")
    hue, sat, bri, kelvin, _res, power, label, _res2 = struct.unpack(
        _FMT_LIGHT_STATE, payload[:52])
    return {
        "hue": hue,
        "saturation": sat,
        "brightness": bri,
        "kelvin": kelvin,
        "power": power > 0,
        "label": _label(label),
    }


def parse_state_power(payload):
    _need(payload, 2, "StatePower")
    (level,) = struct.unpack(_FMT_STATE_POWER, payload[:2])
    return {"power": level > 0}


def parse_state_group(payload):
    _need(payload, 56, "StateGroup")
    gid, label, updated = struct.unpack(_FMT_STATE_GROUP, payload[:56])
    return {"group_id": gid.hex(), "label": _label(label), "updated_at": updated}


def parse_state_location(payload):
    _need(payload, 56, "StateLocation")
    lid, label, updated = struct.unpack(_FMT_STATE_GROUP, payload[:56])
    return {"location_id": lid.hex(), "label": _label(label), "updated_at": updated}


def parse_state_version(payload):
    # The trailing u32 is deprecated on current firmware - vendor/product only.
    _need(payload, 12, "StateVersion")
    vendor, product = struct.unpack(_FMT_STATE_VERSION, payload[:12])
    return {"vendor": vendor, "product": product}


PARSERS = {
    STATE_SERVICE: parse_state_service,
    LIGHT_STATE: parse_light_state,
    LIGHT_STATE_POWER: parse_state_power,
    STATE_GROUP: parse_state_group,
    STATE_LOCATION: parse_state_location,
    STATE_VERSION: parse_state_version,
}


def parse_payload(msg_type, payload):
    """Parse a payload by message type, or return None for types we don't decode."""
    parser = PARSERS.get(msg_type)
    if parser is None:
        return None
    return parser(payload)


# ── Colour maths ──────────────────────────────────────────────────────────

def clamp_kelvin(kelvin, low=KELVIN_MIN, high=KELVIN_MAX):
    try:
        value = int(round(float(kelvin)))
    except (TypeError, ValueError):
        return 3500
    return max(int(low), min(int(high), value))


def hsbk_from_pct(hue_deg, sat_pct, bri_pct, kelvin):
    """(0-360, 0-100, 0-100, K) -> raw u16 HSBK tuple."""
    hue = int(round((float(hue_deg) % 360.0) / 360.0 * U16))
    sat = int(round(max(0.0, min(100.0, float(sat_pct))) / 100.0 * U16))
    bri = int(round(max(0.0, min(100.0, float(bri_pct))) / 100.0 * U16))
    return (min(hue, U16), min(sat, U16), min(bri, U16), clamp_kelvin(kelvin))


def hsbk_to_pct(hue, saturation, brightness, kelvin):
    """Raw u16 HSBK -> (hue 0-360, sat 0-100, bri 0-100, kelvin)."""
    return (
        hue / float(U16) * 360.0,
        saturation / float(U16) * 100.0,
        brightness / float(U16) * 100.0,
        int(kelvin),
    )


def kelvin_to_rgb(kelvin):
    """Blackbody colour approximation (Tanner Helland).  -> (r, g, b) 0-255.

    Red is non-increasing and blue non-decreasing across the range, which is
    what makes the KelvinSlider gradient read correctly left to right.
    """
    temp = clamp_kelvin(kelvin, 1000, 40000) / 100.0

    if temp <= 66:
        red = 255.0
    else:
        red = 329.698727446 * ((temp - 60) ** -0.1332047592)

    if temp <= 66:
        green = 99.4708025861 * math.log(temp) - 161.1195681661
    else:
        green = 288.1221695283 * ((temp - 60) ** -0.0755148492)

    if temp >= 66:
        blue = 255.0
    elif temp <= 19:
        blue = 0.0
    else:
        blue = 138.5177312231 * math.log(temp - 10) - 305.0447927307

    return tuple(max(0, min(255, int(round(c)))) for c in (red, green, blue))


def hsbk_to_rgb(hue, saturation, brightness, kelvin):
    """Raw u16 HSBK -> displayable (r, g, b) 0-255.

    At zero saturation a LIFX bulb emits white at *kelvin*, so fall back to the
    blackbody curve scaled by brightness rather than HSV (which would be grey).
    """
    h, s, v, k = hsbk_to_pct(hue, saturation, brightness, kelvin)
    scale = v / 100.0
    if saturation == 0:
        r, g, b = kelvin_to_rgb(k)
        return (int(round(r * scale)), int(round(g * scale)), int(round(b * scale)))
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, s / 100.0, scale)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def rgb_to_hsbk(r, g, b, kelvin=3500):
    """(0-255, 0-255, 0-255) -> raw u16 HSBK."""
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return hsbk_from_pct(h * 360.0, s * 100.0, v * 100.0, kelvin)


NAMED_COLORS = {
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "orange": (255, 132, 0),
    "yellow": (255, 240, 0),
    "green": (0, 255, 0),
    "cyan": (0, 255, 255),
    "blue": (0, 0, 255),
    "purple": (128, 0, 255),
    "magenta": (255, 0, 255),
    "pink": (255, 105, 180),
    "teal": (0, 128, 128),
    "lime": (128, 255, 0),
    "gold": (255, 200, 60),
    "warm": (255, 180, 100),
    "cool": (200, 220, 255),
    "daylight": (255, 255, 251),
}

_KELVIN_WORDS = {
    "candle": 1500,
    "warmwhite": 2700,
    "softwhite": 3000,
    "neutral": 4000,
    "coolwhite": 5000,
    "daylightwhite": 6500,
}


def parse_color_string(text):
    """Parse '#ff8800', 'FF8800', 'red', '3500k' -> dict, or None if unparseable.

    Returns user units: {"hue": 0-360, "saturation": 0-100, "brightness": 0-100
    or None, "kelvin": int}.  ``brightness`` is None for a pure kelvin string so
    the caller can leave the bulb's current level alone.
    """
    if not text:
        return None
    raw = str(text).strip().lower()
    if not raw:
        return None

    # "3500k" / "3500 k"
    kelvin_text = raw.replace(" ", "")
    if kelvin_text.endswith("k") and kelvin_text[:-1].isdigit():
        return {"hue": 0.0, "saturation": 0.0, "brightness": None,
                "kelvin": clamp_kelvin(int(kelvin_text[:-1]))}

    word = raw.replace(" ", "").replace("_", "")
    if word in _KELVIN_WORDS:
        return {"hue": 0.0, "saturation": 0.0, "brightness": None,
                "kelvin": _KELVIN_WORDS[word]}

    rgb = NAMED_COLORS.get(word)
    if rgb is None:
        hex_text = raw[1:] if raw.startswith("#") else raw
        if len(hex_text) == 3 and all(c in "0123456789abcdef" for c in hex_text):
            hex_text = "".join(c * 2 for c in hex_text)
        if len(hex_text) == 6 and all(c in "0123456789abcdef" for c in hex_text):
            rgb = tuple(int(hex_text[i:i + 2], 16) for i in (0, 2, 4))

    if rgb is None:
        return None

    h, s, v = colorsys.rgb_to_hsv(*[c / 255.0 for c in rgb])
    return {
        "hue": h * 360.0,
        "saturation": s * 100.0,
        "brightness": v * 100.0,
        "kelvin": 3500,
    }


# ── Product capabilities ──────────────────────────────────────────────────
#
# There is no LAN message that reports whether a bulb does colour or what its
# kelvin range is, so it has to be looked up from the product id in
# StateVersion (33).  Subset of LIFX's published products.json covering the
# bulbs people actually own; unknown ids fall back to a permissive default.

_DEFAULT_PRODUCT = {"name": "LIFX", "color": True, "kelvin": (KELVIN_MIN, KELVIN_MAX)}

_COLOR_2500 = (2500, 9000)
_COLOR_1500 = (1500, 9000)
_WW_2700 = (2700, 6500)
_WW_1500 = (1500, 4000)
_FIXED_2700 = (2700, 2700)

PRODUCTS = {
    1:   ("Original 1000", True, _COLOR_2500),
    3:   ("Color 650", True, _COLOR_2500),
    10:  ("White 800", False, _WW_2700),
    11:  ("White 800", False, _WW_2700),
    15:  ("Color 1000", True, _COLOR_2500),
    18:  ("White 900 BR30", False, _WW_2700),
    19:  ("White 900 BR30", False, _WW_2700),
    20:  ("Color 1000 BR30", True, _COLOR_2500),
    22:  ("Color 1000", True, _COLOR_2500),
    27:  ("LIFX A19", True, _COLOR_2500),
    28:  ("LIFX BR30", True, _COLOR_2500),
    29:  ("LIFX+ A19", True, _COLOR_2500),
    30:  ("LIFX+ BR30", True, _COLOR_2500),
    31:  ("LIFX Z", True, _COLOR_2500),
    32:  ("LIFX Z 2", True, _COLOR_2500),
    36:  ("LIFX Downlight", True, _COLOR_2500),
    37:  ("LIFX Downlight", True, _COLOR_2500),
    38:  ("LIFX Beam", True, _COLOR_2500),
    39:  ("LIFX Downlight White to Warm", False, _WW_1500),
    40:  ("LIFX Downlight", True, _COLOR_2500),
    43:  ("LIFX A19", True, _COLOR_2500),
    44:  ("LIFX BR30", True, _COLOR_2500),
    45:  ("LIFX+ A19", True, _COLOR_2500),
    46:  ("LIFX+ BR30", True, _COLOR_2500),
    49:  ("LIFX Mini Color", True, _COLOR_1500),
    50:  ("LIFX Mini White to Warm", False, _WW_1500),
    51:  ("LIFX Mini White", False, _FIXED_2700),
    52:  ("LIFX GU10", True, _COLOR_1500),
    53:  ("LIFX GU10", True, _COLOR_1500),
    55:  ("LIFX Tile", True, _COLOR_2500),
    57:  ("LIFX Candle", True, _COLOR_1500),
    59:  ("LIFX Mini Color", True, _COLOR_1500),
    60:  ("LIFX Mini White to Warm", False, _WW_1500),
    61:  ("LIFX Mini White", False, _FIXED_2700),
    62:  ("LIFX A19", True, _COLOR_2500),
    63:  ("LIFX BR30", True, _COLOR_2500),
    64:  ("LIFX+ A19", True, _COLOR_2500),
    65:  ("LIFX+ BR30", True, _COLOR_2500),
    66:  ("LIFX Mini White", False, _FIXED_2700),
    68:  ("LIFX Candle", True, _COLOR_1500),
    81:  ("LIFX Candle White to Warm", False, (2200, 6500)),
    82:  ("LIFX Filament Clear", False, (2100, 2100)),
    85:  ("LIFX Filament Amber", False, (2000, 2000)),
    87:  ("LIFX Mini White", False, _FIXED_2700),
    88:  ("LIFX Mini White", False, _FIXED_2700),
    90:  ("LIFX Clean", True, _COLOR_1500),
    91:  ("LIFX Color", True, _COLOR_1500),
    92:  ("LIFX Color", True, _COLOR_1500),
    93:  ("LIFX A19", True, _COLOR_1500),
    94:  ("LIFX BR30", True, _COLOR_1500),
    96:  ("LIFX Candle White to Warm", False, (2200, 6500)),
    97:  ("LIFX A19", True, _COLOR_1500),
    98:  ("LIFX BR30", True, _COLOR_1500),
    99:  ("LIFX Clean", True, _COLOR_1500),
    100: ("LIFX Filament Clear", False, (2100, 2100)),
    101: ("LIFX Filament Amber", False, (2000, 2000)),
    109: ("LIFX A19 Night Vision", True, _COLOR_1500),
    110: ("LIFX BR30 Night Vision", True, _COLOR_1500),
    111: ("LIFX A19 Night Vision", True, _COLOR_1500),
    112: ("LIFX BR30 Night Vision", True, _COLOR_1500),
    113: ("LIFX Mini White to Warm", False, _WW_1500),
    114: ("LIFX Mini White to Warm", False, _WW_1500),
    117: ("LIFX Z", True, _COLOR_1500),
    118: ("LIFX Z", True, _COLOR_1500),
    119: ("LIFX Beam", True, _COLOR_1500),
    120: ("LIFX Beam", True, _COLOR_1500),
    121: ("LIFX Downlight", True, _COLOR_1500),
    122: ("LIFX Downlight", True, _COLOR_1500),
    123: ("LIFX Color", True, _COLOR_1500),
    124: ("LIFX Color", True, _COLOR_1500),
    125: ("LIFX White to Warm", False, _WW_1500),
    126: ("LIFX White to Warm", False, _WW_1500),
    127: ("LIFX White", False, _FIXED_2700),
    128: ("LIFX White", False, _FIXED_2700),
    129: ("LIFX Color", True, _COLOR_1500),
    130: ("LIFX Color", True, _COLOR_1500),
    131: ("LIFX White to Warm", False, _WW_1500),
    132: ("LIFX White to Warm", False, _WW_1500),
    137: ("LIFX Candle Color", True, _COLOR_1500),
    141: ("LIFX Neon", True, _COLOR_1500),
    142: ("LIFX Neon", True, _COLOR_1500),
    143: ("LIFX String", True, _COLOR_1500),
    171: ("LIFX Ceiling", True, _COLOR_1500),
}


def product_info(product_id):
    """-> {"name": str, "color": bool, "kelvin": (low, high)} - never raises."""
    entry = PRODUCTS.get(product_id)
    if entry is None:
        return dict(_DEFAULT_PRODUCT)
    name, color, kelvin = entry
    return {"name": name, "color": color, "kelvin": kelvin}
