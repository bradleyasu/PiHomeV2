"""Pure-Python state logic for the BambuLab screen and its background service.

Deliberately free of Kivy imports so it can be unit-tested headlessly (see
``screens/BambuLab/tests/test_core.py``) — the same split used by
``screens/BluetoothConnect/protocol.py`` and ``screens/Calendar/calstore.py``.

Holds three things:

  * The MQTT payload parser (``parse_print``) that turns a printer report into a
    plain snapshot dict, plus the alert/filament formatters it uses.
  * The trigger vocabulary and edge detection (``triggers_fired``) that the
    service uses to decide when a state-alert rule should fire.
  * ``substitute``, which injects snapshot values into a rule's nested event.
"""

# Placeholder substitution is shared with every other rule store; re-exported
# here so this module stays the single import for BambuLab's state logic.
from util.rulestore import substitute  # noqa: F401

# ── Colors ─────────────────────────────────────────────────────────────────────

# BambuLab brand green
ACCENT = (0.0, 0.68, 0.26, 1.0)

# Pre-allocated color lists — avoids creating new list objects on every MQTT message
COLOR_ACCENT = list(ACCENT)
COLOR_IDLE   = [0.45, 0.45, 0.45, 1]
COLOR_PAUSE  = [0.95, 0.65, 0.10, 1]
COLOR_FAILED = [0.85, 0.25, 0.25, 1]
COLOR_FINISH = [0.20, 0.60, 0.95, 1]
COLOR_ERROR  = [0.85, 0.25, 0.25, 1]

STATE_LABELS = {
    "IDLE":    "IDLE",
    "PREPARE": "PREPARING",
    "SLICING": "SLICING",
    "RUNNING": "PRINTING",
    "PAUSE":   "PAUSED",
    "FINISH":  "COMPLETE",
    "FAILED":  "FAILED",
    "OFFLINE": "OFFLINE",
}

STATE_COLORS = {
    "RUNNING": COLOR_ACCENT,
    "PAUSE":   COLOR_PAUSE,
    "FAILED":  COLOR_FAILED,
    "FINISH":  COLOR_FINISH,
    "PREPARE": COLOR_PAUSE,
    "SLICING": COLOR_PAUSE,
}


def resolve_state_color(state):
    return STATE_COLORS.get(state, COLOR_IDLE)


def state_label(state):
    return STATE_LABELS.get(state, state or "IDLE")


# ── Triggers ───────────────────────────────────────────────────────────────────

# gcode_state values a rule may bind to.
GCODE_TRIGGERS = ("IDLE", "PREPARE", "SLICING", "RUNNING", "PAUSE", "FINISH", "FAILED")

# Pseudo-states derived from something other than gcode_state.
PSEUDO_TRIGGERS = ("ERROR", "ONLINE", "OFFLINE")

TRIGGERS = GCODE_TRIGGERS + PSEUDO_TRIGGERS

# Human phrasings accepted in place of the canonical token, so a rule can be
# written as "printing" or "complete" rather than the printer's raw vocabulary.
TRIGGER_ALIASES = {
    "PRINTING":  "RUNNING",
    "RUN":       "RUNNING",
    "PAUSED":    "PAUSE",
    "COMPLETE":  "FINISH",
    "COMPLETED": "FINISH",
    "DONE":      "FINISH",
    "FINISHED":  "FINISH",
    "FAIL":      "FAILED",
    "FAILURE":   "FAILED",
    "PREPARING": "PREPARE",
    "SLICE":     "SLICING",
    "ERR":       "ERROR",
    "CONNECTED":    "ONLINE",
    "DISCONNECTED": "OFFLINE",
}

# Descriptions surfaced in the event-builder dropdown (to_definition options).
TRIGGER_LABELS = {
    "IDLE":    "IDLE (printer idle)",
    "PREPARE": "PREPARE (preparing to print)",
    "SLICING": "SLICING",
    "RUNNING": "RUNNING (printing)",
    "PAUSE":   "PAUSE (print paused)",
    "FINISH":  "FINISH (print complete)",
    "FAILED":  "FAILED (print failed)",
    "ERROR":   "ERROR (print error or HMS alert raised)",
    "ONLINE":  "ONLINE (printer reachable)",
    "OFFLINE": "OFFLINE (printer unreachable)",
}


def normalize_trigger(value):
    """Map user input onto a canonical trigger token, or None if unrecognized."""
    token = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if not token:
        return None
    token = TRIGGER_ALIASES.get(token, token)
    return token if token in TRIGGERS else None


def new_snapshot():
    """A blank snapshot — the shape every consumer can rely on."""
    return {
        "connected": False,
        "connection_state": "disconnected",   # disconnected | connected | error
        "connection_label": "DISCONNECTED",
        "gcode_state": "IDLE",
        "state_label": "IDLE",
        "job_name": "No Active Print",
        "progress": 0,
        "layer_current": 0,
        "layer_total": 0,
        "eta_minutes": 0,
        "nozzle": 0.0,
        "nozzle_target": 0.0,
        "bed": 0.0,
        "bed_target": 0.0,
        "chamber": 0.0,
        "speed": -1,
        "filament_type": "—",
        "filament_color": None,
        "alert_active": False,
        "alert_text": "",
        "alert_severe": True,
        # True once a real report has been applied. The service uses this to
        # establish a baseline without firing rules on the first message.
        "seeded": False,
    }


def triggers_fired(prev, new):
    """Return the trigger tokens that this snapshot transition satisfies.

    Edge-triggered: a trigger fires only on *entering* its condition, so a rule
    never re-fires while the printer sits in the same state.

    ONLINE/OFFLINE ride on the connection flags and always fire on their edge.
    The printer-state triggers additionally require both snapshots to be
    ``seeded`` — the first report after a connect is a baseline, not an event, so
    a restart or a brief network blip cannot replay a stale completion.
    """
    if not prev:
        return []

    fired = []

    if prev.get("seeded") and new.get("seeded"):
        state = new.get("gcode_state")
        if state != prev.get("gcode_state") and state in GCODE_TRIGGERS:
            fired.append(state)

        # ERROR is separate from FAILED: it covers print_error / HMS health
        # alerts (filament runout, door open, ...) which the printer raises
        # without necessarily failing the job.
        if new.get("alert_active") and not prev.get("alert_active"):
            fired.append("ERROR")

    if new.get("connected") and not prev.get("connected"):
        fired.append("ONLINE")
    elif prev.get("connected") and not new.get("connected"):
        fired.append("OFFLINE")

    return fired


# ── Placeholder substitution ───────────────────────────────────────────────────

def placeholder_values(snapshot):
    """Build the ``$name`` -> string map a rule's event can interpolate."""
    snap = snapshot or {}
    layer_total = snap.get("layer_total", 0)
    eta = int(snap.get("eta_minutes", 0) or 0)
    return {
        "state":       str(snap.get("gcode_state", "")),
        "state_label": str(snap.get("state_label", "")),
        "job":         str(snap.get("job_name", "")),
        "progress":    str(int(snap.get("progress", 0) or 0)),
        "layer":       str(int(snap.get("layer_current", 0) or 0)),
        "layer_total": str(int(layer_total or 0)),
        "eta":         str(eta),
        "eta_text":    format_eta(eta),
        "finish":      format_finish(eta, snap.get("gcode_state")),
        "error":       str(snap.get("alert_text", "")),
        "nozzle":      "{:.0f}".format(snap.get("nozzle", 0.0) or 0.0),
        "bed":         "{:.0f}".format(snap.get("bed", 0.0) or 0.0),
    }


# ── Formatting helpers (shared by the screen and by placeholders) ──────────────

def format_temp(current, target):
    """Show 'current / target' when actively heating to a setpoint, else just current."""
    if target and target > 0:
        return f"{current:.0f}° / {target:.0f}°C"
    return f"{current:.1f}°C"


def format_eta(minutes):
    """Format remaining minutes as 'ETA  Xh Ym' for long prints, 'ETA  N min' otherwise."""
    m = int(minutes or 0)
    if m <= 0:
        return "—"
    if m < 60:
        return f"ETA  {m} min"
    hours, mins = divmod(m, 60)
    if mins == 0:
        return f"ETA  {hours}h"
    return f"ETA  {hours}h {mins}m"


def format_finish(minutes, state, now=None):
    """Estimated wall-clock finish time, e.g. 'Done 3:42 PM'. Empty unless RUNNING."""
    import datetime

    m = int(minutes or 0)
    if m <= 0 or state != "RUNNING":
        return ""
    base = now or datetime.datetime.now()
    finish = base + datetime.timedelta(minutes=m)
    # %-I strips the leading zero from the hour (Linux/macOS). Pi runs Linux.
    return "Done " + finish.strftime("%-I:%M %p")


# ── Payload parsing ────────────────────────────────────────────────────────────

def safe_int(value, fallback):
    """Convert value to int, returning fallback on None or error."""
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def safe_float(value, fallback):
    """Convert value to float, returning fallback on None or error."""
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def parse_print(p, snapshot):
    """Apply one printer report (payload["print"]) onto a snapshot dict.

    Returns a NEW dict — callers compare it against the previous snapshot to
    detect transitions. Absent keys keep their previous value because the P1
    series sends deltas rather than full state.
    """
    snap = dict(snapshot or new_snapshot())

    state = p.get("gcode_state")
    if state is not None:
        snap["gcode_state"] = state
        snap["state_label"] = state_label(state)

    snap["progress"]      = safe_int(p.get("mc_percent"), snap["progress"])
    snap["layer_current"] = safe_int(p.get("layer_num"), snap["layer_current"])
    snap["layer_total"]   = safe_int(p.get("total_layer_num"), snap["layer_total"])
    snap["eta_minutes"]   = safe_int(p.get("mc_remaining_time"), snap["eta_minutes"])
    snap["nozzle"]        = safe_float(p.get("nozzle_temper"), snap["nozzle"])
    snap["bed"]           = safe_float(p.get("bed_temper"), snap["bed"])
    snap["nozzle_target"] = safe_float(p.get("nozzle_target_temper"), snap["nozzle_target"])
    snap["bed_target"]    = safe_float(p.get("bed_target_temper"), snap["bed_target"])

    # chamber_temper was removed in recent firmware; fall back to the nested
    # device -> ctc -> info -> temp path used by X1C.
    chamber = p.get("chamber_temper")
    if chamber is None:
        try:
            chamber = p["device"]["ctc"]["info"]["temp"]
        except (KeyError, TypeError):
            pass
    snap["chamber"] = safe_float(chamber, snap["chamber"])
    snap["speed"]   = safe_int(p.get("spd_mag"), snap["speed"])

    job = p.get("subtask_name") or p.get("gcode_file")
    if job:
        snap["job_name"] = job

    ams_data = p.get("ams")
    if isinstance(ams_data, dict):
        name, rgba = resolve_filament(ams_data, p.get("vt_tray"))
        if name:
            snap["filament_type"] = name
        snap["filament_color"] = rgba

    # Health-management (HMS) alerts + print errors. Only update when the printer
    # included these keys in this report (P1 sends deltas).
    if "hms" in p or "print_error" in p:
        alerts = format_alerts(p.get("hms"), p.get("print_error", 0))
        snap["alert_active"] = alerts["active"]
        snap["alert_text"]   = alerts["text"]
        snap["alert_severe"] = alerts["severe"]

    snap["seeded"] = True
    return snap


def format_alerts(hms, print_error):
    """Summarize printer health alerts for the banner.

    HMS entries are pairs of 32-bit ints (``attr``, ``code``). We format the
    canonical ``XXXX_XXXX_XXXX_XXXX`` code (lookup-able on the Bambu wiki) and
    derive a severity from the high word of ``code``. Exact human-readable text
    isn't in the payload, so we show the code.
    """
    severity_rank = {1: 3, 2: 2, 3: 1, 4: 0}  # fatal > serious > common > info
    codes = []
    worst = -1
    if isinstance(hms, list):
        for item in hms:
            if not isinstance(item, dict):
                continue
            attr = safe_int(item.get("attr"), 0)
            code = safe_int(item.get("code"), 0)
            if attr == 0 and code == 0:
                continue
            sev = (code >> 16) & 0xFFFF
            worst = max(worst, severity_rank.get(sev, 1))
            codes.append(
                "{:04X}_{:04X}_{:04X}_{:04X}".format(
                    (attr >> 16) & 0xFFFF, attr & 0xFFFF,
                    (code >> 16) & 0xFFFF, code & 0xFFFF,
                )
            )

    perr = safe_int(print_error, 0)

    if not codes and perr == 0:
        return {"active": False, "text": "", "severe": True, "codes": []}

    if perr != 0 and not codes:
        return {"active": True, "text": f"Print Error  0x{perr:08X}",
                "severe": True, "codes": []}

    first = codes[0]
    extra = f"  (+{len(codes) - 1} more)" if len(codes) > 1 else ""
    return {"active": True, "text": f"HMS  {first}{extra}",
            # Serious/fatal -> red, common/info -> amber
            "severe": worst >= 2, "codes": codes}


def resolve_filament(ams_data, vt_tray):
    """Resolve the active spool to a (name, rgba) pair.

    The printer reports the loaded slot in ``tray_now`` (0-3 for AMS slots,
    254/255 for the external spool). We select that tray rather than the first
    non-empty one so the display matches what is actually printing. ``rgba`` is
    None when the slot has no usable color.
    """
    tray_now = str(ams_data.get("tray_now", "255"))
    active = None

    if tray_now in ("254", "255"):
        # External (vt_tray) spool
        if isinstance(vt_tray, dict) and vt_tray.get("tray_type"):
            active = vt_tray
    else:
        for ams_unit in ams_data.get("ams", []):
            for tray in ams_unit.get("tray", []):
                if str(tray.get("id")) == tray_now and tray.get("tray_type"):
                    active = tray
                    break
            if active:
                break

    # Fallback: first loaded tray if the active slot couldn't be resolved
    if active is None:
        for ams_unit in ams_data.get("ams", []):
            for tray in ams_unit.get("tray", []):
                if tray.get("tray_type"):
                    active = tray
                    break
            if active:
                break

    if active is None:
        return None, None

    # Prefer the descriptive sub-brand ("PLA Matte"), fall back to type ("PLA")
    name = (active.get("tray_sub_brands") or active.get("tray_type") or "").strip()
    return (name or None), hex_to_rgba(active.get("tray_color", ""))


def hex_to_rgba(hexstr):
    """Convert a Bambu 'RRGGBBAA' hex string to an opaque [r,g,b,1] list.

    Returns None for empty/transparent values (e.g. an unloaded slot) so the
    swatch can be hidden.
    """
    hexstr = (hexstr or "").strip()
    if len(hexstr) < 6:
        return None
    try:
        r = int(hexstr[0:2], 16) / 255.0
        g = int(hexstr[2:4], 16) / 255.0
        b = int(hexstr[4:6], 16) / 255.0
        a = int(hexstr[6:8], 16) / 255.0 if len(hexstr) >= 8 else 1.0
    except ValueError:
        return None
    if a == 0:
        return None  # fully transparent — treat as "no color"
    # Force opaque so the swatch is always visible regardless of source alpha
    return [r, g, b, 1.0]
