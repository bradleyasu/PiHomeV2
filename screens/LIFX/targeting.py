"""Resolving a user-supplied target string to a set of LIFX bulbs.

Pure functions over a plain registry dict - no Kivy, no network, no imports
beyond the protocol module, so the matching rules can be tested directly::

    python3 screens/LIFX/tests/test_targeting.py

The registry is ``{serial: entry}`` and is also exactly what gets written to
``cache/lifx_devices.json``.  One entry::

    {"serial", "ip", "port", "label", "group", "group_id", "location",
     "location_id", "product", "color": bool, "kelvin_range": [lo, hi],
     "hue", "saturation", "brightness", "kelvin",   # raw u16 except kelvin
     "power": bool, "seen_at": float, "online": bool}
"""

from screens.LIFX.protocol import (
    KELVIN_MAX,
    KELVIN_MIN,
    U16,
    hsbk_to_pct,
    normalize_serial,
)

TARGET_ALL = "all"
_ALL_WORDS = ("", "all", "*", "everything", "all lights")

KIND_ALL = "all"
KIND_BULB = "bulb"
KIND_GROUP = "group"

UNGROUPED = "Ungrouped"


class TargetError(Exception):
    """A target string could not be resolved.  Carries the HTTP-ish response shape."""

    def __init__(self, code, error_code, message, candidates=None):
        super().__init__(message)
        self.code = code
        self.error_code = error_code
        self.message = message
        self.candidates = candidates or []


# ── Resolution ────────────────────────────────────────────────────────────

def _online(entry):
    return entry.get("online", True)


def _all_serials(registry, online_only=True):
    serials = [s for s, e in registry.items() if not online_only or _online(e)]
    return sorted(serials, key=lambda s: (registry[s].get("label") or "").lower())


def _by_group(registry):
    """-> {lowercased group label: [serial, ...]}"""
    out = {}
    for serial, entry in registry.items():
        name = (entry.get("group") or UNGROUPED).strip()
        out.setdefault(name.lower(), []).append(serial)
    return out


def _by_location(registry):
    out = {}
    for serial, entry in registry.items():
        name = (entry.get("location") or "").strip()
        if name:
            out.setdefault(name.lower(), []).append(serial)
    return out


def _by_label(registry):
    """-> {lowercased bulb label: [serial, ...]} (labels are not guaranteed unique)."""
    out = {}
    for serial, entry in registry.items():
        name = (entry.get("label") or "").strip()
        if name:
            out.setdefault(name.lower(), []).append(serial)
    return out


def _display_name(registry, serials, fallback):
    if len(serials) == 1:
        return registry[serials[0]].get("label") or fallback
    return fallback


def resolve_target(registry, target, target_type="auto"):
    """-> (serials, kind, resolved_name).  Raises :class:`TargetError`.

    An exact *group* name beats an exact *bulb* name, so "Kitchen" means the
    whole room even when a bulb is also called "Kitchen".  Pass
    ``target_type="bulb"`` to force the other reading.
    """
    if not registry:
        raise TargetError(503, "no_devices", "No LIFX bulbs discovered yet")

    kind_filter = (target_type or "auto").strip().lower()
    if kind_filter not in ("auto", KIND_BULB, KIND_GROUP, KIND_ALL):
        raise TargetError(400, "bad_request",
                          "target_type must be auto, bulb, group or all")

    text = ("" if target is None else str(target)).strip()

    # 1. Everything.
    if kind_filter == KIND_ALL or (kind_filter == "auto"
                                   and text.lower() in _ALL_WORDS):
        serials = _all_serials(registry)
        if not serials:
            raise TargetError(503, "no_devices", "No LIFX bulbs are online")
        return serials, KIND_ALL, "All Lights"

    if not text:
        raise TargetError(400, "bad_request",
                          "target is required when target_type is {}".format(kind_filter))

    lowered = text.lower()
    groups = _by_group(registry)
    locations = _by_location(registry)
    labels = _by_label(registry)

    want_bulb = kind_filter in ("auto", KIND_BULB)
    want_group = kind_filter in ("auto", KIND_GROUP)

    # 2. An explicit serial always wins - it is unambiguous by construction.
    if want_bulb:
        serial = normalize_serial(text)
        if serial and serial in registry:
            return [serial], KIND_BULB, registry[serial].get("label") or serial

    # 3. Exact group name, then exact bulb name, then exact location name.
    if want_group and lowered in groups:
        serials = sorted(groups[lowered])
        return serials, KIND_GROUP, _canonical_group(registry, serials)

    if want_bulb and lowered in labels:
        serials = sorted(labels[lowered])
        kind = KIND_BULB if len(serials) == 1 else KIND_GROUP
        return serials, kind, registry[serials[0]].get("label") or text

    if want_group and lowered in locations:
        serials = sorted(locations[lowered])
        return serials, KIND_GROUP, registry[serials[0]].get("location") or text

    # 4. Unique case-insensitive prefix across whichever namespaces are in play.
    matches = {}
    if want_group:
        for name, serials in groups.items():
            if name.startswith(lowered):
                matches[("group", name)] = serials
        for name, serials in locations.items():
            if name.startswith(lowered):
                matches.setdefault(("group", name), serials)
    if want_bulb:
        for name, serials in labels.items():
            if name.startswith(lowered):
                matches[("bulb", name)] = serials

    if len(matches) == 1:
        (kind, _name), serials = next(iter(matches.items()))
        serials = sorted(serials)
        if kind == "group":
            return serials, KIND_GROUP, _canonical_group(registry, serials)
        resolved = registry[serials[0]].get("label") or text
        return serials, KIND_BULB if len(serials) == 1 else KIND_GROUP, resolved

    if len(matches) > 1:
        candidates = sorted(_pretty_name(registry, kind, name)
                            for (kind, name) in matches)
        raise TargetError(
            409, "ambiguous_target",
            "'{}' matches {}".format(text, ", ".join(candidates)),
            candidates=candidates)

    noun = {"bulb": "bulb", "group": "room"}.get(kind_filter, "bulb or room")
    error_code = "group_not_found" if kind_filter == KIND_GROUP else "bulb_not_found"
    raise TargetError(404, error_code,
                      "No LIFX {} named '{}'".format(noun, text))


def _canonical_group(registry, serials):
    """The group label with its original capitalisation."""
    for serial in serials:
        name = registry[serial].get("group")
        if name:
            return name
    return UNGROUPED


def _pretty_name(registry, kind, lowered):
    source = "group" if kind == "group" else "label"
    for entry in registry.values():
        value = entry.get(source) or ""
        if value.lower() == lowered:
            return value
    return lowered


# ── Grouping and summarising for the UI ───────────────────────────────────

def group_index(registry):
    """Rooms sorted by name, with Ungrouped last.

    -> [{"name", "group_id", "serials", "count", "on_count", "any_on",
         "brightness"}]
    """
    buckets = {}
    for serial, entry in registry.items():
        name = (entry.get("group") or UNGROUPED).strip() or UNGROUPED
        bucket = buckets.setdefault(name, {"name": name,
                                           "group_id": entry.get("group_id") or "",
                                           "serials": []})
        bucket["serials"].append(serial)

    rooms = []
    for bucket in buckets.values():
        bucket["serials"].sort(
            key=lambda s: ((registry[s].get("label") or "").lower(), s))
        stats = summarize(registry, bucket["serials"])
        bucket.update({
            "count": stats["count"],
            "on_count": stats["on_count"],
            "any_on": stats["any_on"],
            "brightness": stats["brightness"],
        })
        rooms.append(bucket)

    rooms.sort(key=lambda r: (r["name"] == UNGROUPED, r["name"].lower()))
    return rooms


def summarize(registry, serials):
    """Aggregate state for a selection, for the control panel header.

    Brightness averages the bulbs that are *on* (an off bulb reporting its
    last level would otherwise drag the slider down).  Colour is taken from
    the first lit colour-capable bulb so the wheel lands somewhere meaningful.
    """
    entries = [registry[s] for s in serials if s in registry]
    empty = {
        "count": 0, "on_count": 0, "any_on": False, "all_on": False,
        "online": 0, "brightness": 0.0, "hue": 0.0, "saturation": 0.0,
        "kelvin": 3500, "supports_color": True,
        "kelvin_range": (KELVIN_MIN, KELVIN_MAX), "rgb": (0, 0, 0),
    }
    if not entries:
        return empty

    lit = [e for e in entries if e.get("power")]
    source = None
    for entry in lit:
        if entry.get("color", True):
            source = entry
            break
    if source is None:
        source = lit[0] if lit else entries[0]

    hue, sat, bri, kelvin = hsbk_to_pct(
        source.get("hue", 0) or 0,
        source.get("saturation", 0) or 0,
        source.get("brightness", 0) or 0,
        source.get("kelvin", 3500) or 3500,
    )

    measured = lit or entries
    brightness = sum(
        (e.get("brightness", 0) or 0) / float(U16) * 100.0 for e in measured
    ) / len(measured)

    return {
        "count": len(entries),
        "on_count": len(lit),
        "any_on": bool(lit),
        "all_on": len(lit) == len(entries),
        "online": sum(1 for e in entries if _online(e)),
        "brightness": brightness,
        "hue": hue,
        "saturation": sat,
        "kelvin": kelvin,
        "supports_color": any(e.get("color", True) for e in entries),
        "kelvin_range": merge_kelvin_ranges(entries),
        "rgb": (0, 0, 0),
    }


def merge_kelvin_ranges(entries):
    """Intersect the selection's kelvin ranges, widening if they don't overlap.

    Mixing a fixed-2700K bulb with a 1500-4000K one has an empty intersection;
    a slider with no travel is worse than one that overshoots a bulb which
    will clamp the value itself anyway.
    """
    ranges = []
    for entry in entries:
        raw = entry.get("kelvin_range") or (KELVIN_MIN, KELVIN_MAX)
        try:
            low, high = int(raw[0]), int(raw[1])
        except (TypeError, ValueError, IndexError):
            low, high = KELVIN_MIN, KELVIN_MAX
        if low > high:
            low, high = high, low
        ranges.append((low, high))

    if not ranges:
        return (KELVIN_MIN, KELVIN_MAX)

    low = max(r[0] for r in ranges)
    high = min(r[1] for r in ranges)
    if low >= high:
        return (min(r[0] for r in ranges), max(r[1] for r in ranges))
    return (low, high)
