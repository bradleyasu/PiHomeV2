"""Headless calendar data layer for the Calendar screen.

Pure Python, NO Kivy imports — so it can be unit-tested without a display and
shared by both the screen (rendering) and the always-on service (reminders).

Responsibilities:
  * Persist the user's list of calendars (name + Secret iCal URL + color).
  * Fetch each calendar's private ``.ics`` feed over HTTPS and expand recurring
    (RRULE) events into concrete occurrences over a date window.
  * Normalize every occurrence to a JSON-friendly dict and cache the merged,
    sorted result so the screen renders instantly and reminders work headless.
  * Pure helpers for the reminder-window logic (testable without the network).

The ICS libraries (``icalendar`` + ``recurring_ical_events``) are declared in the
manifest's ``dependencies`` and auto-install on first boot (then a restart). Until
then ``AVAILABLE`` is False and the network paths degrade gracefully; the calendar
list / cache I/O and reminder math never need those libraries.
"""

import json
import os
from datetime import datetime, date, timedelta

import requests

from util.phlog import PIHOME_LOGGER

# ── Persistent files (cache/ is gitignored; secrets live here, never in the repo) ──
CALENDARS_FILE = "cache/calendar_sources.json"   # [{id,name,url,color,enabled}]
EVENTS_FILE    = "cache/calendar_events.json"       # {fetched_at, window_start, window_end, events:[...]}

_HTTP_TIMEOUT = 20  # seconds

# Local timezone of the running device — occurrences are converted into this.
def _local_tz():
    return datetime.now().astimezone().tzinfo

# Default color palette handed out to new calendars (hex, no leading #).
COLOR_PALETTE = ["4C8BF5", "E8633A", "3BB273", "B569D6", "E0B341", "37A6C4"]

# Whether the ICS parsing libraries are importable in this process.
try:
    import icalendar  # noqa: F401
    import recurring_ical_events  # noqa: F401
    AVAILABLE = True
except Exception:
    AVAILABLE = False


# ── Generic JSON persistence ────────────────────────────────────────────────

def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception as e:
        PIHOME_LOGGER.error(f"Calendar: failed to read {path}: {e}")
    return default


def _save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        PIHOME_LOGGER.error(f"Calendar: failed to write {path}: {e}")


# ── Calendar list ───────────────────────────────────────────────────────────

def load_calendars():
    """Return the configured calendar list (possibly empty)."""
    data = _load_json(CALENDARS_FILE, [])
    return data if isinstance(data, list) else []


def save_calendars(calendars):
    _save_json(CALENDARS_FILE, calendars)


def add_calendar(name, url, color=None, enabled=True):
    """Append a calendar, assigning an id and a palette color if none given."""
    cals = load_calendars()
    cid = "cal_{}".format(int(datetime.now().timestamp() * 1000))
    if not color:
        color = COLOR_PALETTE[len(cals) % len(COLOR_PALETTE)]
    cals.append({
        "id": cid,
        "name": (name or "Calendar").strip(),
        "url": (url or "").strip(),
        "color": color,
        "enabled": bool(enabled),
    })
    save_calendars(cals)
    return cid


def remove_calendar(cid):
    cals = [c for c in load_calendars() if c.get("id") != cid]
    save_calendars(cals)


# ── ICS fetch + parse + recurrence expansion ─────────────────────────────────

def fetch_ics(url):
    """Download a calendar's iCal feed. Returns the text body, or raises."""
    resp = requests.get(url, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _to_local_iso(value):
    """Normalize an icalendar DTSTART/DTEND value to (iso_string, all_day).

    DATE values (no time) are all-day; datetimes are converted to local time
    (naive datetimes are assumed to already be local/floating).
    """
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(_local_tz())
        return value.isoformat(), False
    if isinstance(value, date):
        return value.isoformat(), True
    return str(value), False


def parse_ics(text, window_start, window_end, calendar_id="", calendar_name="", color=""):
    """Expand an iCal feed into normalized occurrence dicts within the window.

    Requires the optional ICS libraries; returns [] (and logs) if unavailable or
    on parse error so one bad feed never breaks the others.
    """
    if not AVAILABLE:
        return []
    try:
        import icalendar
        import recurring_ical_events
    except Exception as e:
        PIHOME_LOGGER.error(f"Calendar: ICS libs unavailable: {e}")
        return []

    try:
        cal = icalendar.Calendar.from_ical(text)
    except Exception as e:
        PIHOME_LOGGER.error(f"Calendar: failed to parse feed '{calendar_name}': {e}")
        return []

    try:
        occurrences = recurring_ical_events.of(cal).between(window_start, window_end)
    except Exception as e:
        PIHOME_LOGGER.error(f"Calendar: failed to expand feed '{calendar_name}': {e}")
        return []

    events = []
    for comp in occurrences:
        try:
            dtstart = comp.get("DTSTART")
            if dtstart is None:
                continue
            start_iso, all_day = _to_local_iso(dtstart.dt)
            dtend = comp.get("DTEND")
            end_iso = _to_local_iso(dtend.dt)[0] if dtend is not None else start_iso
            events.append({
                "uid": str(comp.get("UID", "")),
                "calendar_id": calendar_id,
                "calendar_name": calendar_name,
                "color": color,
                "title": str(comp.get("SUMMARY", "(no title)")),
                "location": str(comp.get("LOCATION", "")),
                "start": start_iso,
                "end": end_iso,
                "all_day": all_day,
            })
        except Exception as e:
            PIHOME_LOGGER.error(f"Calendar: skipped a malformed event in '{calendar_name}': {e}")
    return events


def refresh_window(window_start, window_end):
    """Fetch every enabled calendar, merge + sort occurrences, write the cache.

    A per-calendar fetch/parse failure is logged and skipped — the other
    calendars still render. Returns the merged event list.
    """
    merged = []
    for cal in load_calendars():
        if not cal.get("enabled", True) or not cal.get("url"):
            continue
        try:
            text = fetch_ics(cal["url"])
        except Exception as e:
            PIHOME_LOGGER.error(f"Calendar: fetch failed for '{cal.get('name')}': {e}")
            continue
        merged.extend(parse_ics(
            text, window_start, window_end,
            calendar_id=cal.get("id", ""),
            calendar_name=cal.get("name", ""),
            color=cal.get("color", ""),
        ))

    merged.sort(key=lambda e: e["start"])
    _save_json(EVENTS_FILE, {
        "fetched_at": datetime.now().astimezone().isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "events": merged,
    })
    return merged


def read_events_cache():
    """Return the cached payload ({fetched_at, window_*, events:[...]})."""
    data = _load_json(EVENTS_FILE, {})
    if not isinstance(data, dict):
        return {"events": []}
    data.setdefault("events", [])
    return data


# ── Reminder-window logic (pure + testable) ──────────────────────────────────

def parse_iso(s):
    """Parse an ISO datetime string back into a datetime (or None)."""
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def reminder_key(uid, start_iso, lead_min):
    """Stable dedup key for a single (event-occurrence, lead-time) reminder."""
    return f"{uid}|{start_iso}|{lead_min}"


def compute_due(events, now_dt, leads_min):
    """Yield (event, lead_min, key) for reminders currently due.

    A reminder for lead L is due when ``start - L <= now < start``. All-day
    events have no meaningful clock time, so they get no time-based reminder.
    ``now_dt`` must be timezone-aware (local). Dedup is the caller's job (via
    ``key`` against a persisted fired-set).
    """
    due = []
    for ev in events:
        if ev.get("all_day"):
            continue
        start = parse_iso(ev.get("start", ""))
        if start is None or start.tzinfo is None:
            continue
        if start <= now_dt:
            continue  # already started / past
        for lead in leads_min:
            if lead <= 0:
                continue
            if now_dt >= start - timedelta(minutes=lead):
                due.append((ev, lead, reminder_key(ev.get("uid", ""), ev.get("start", ""), lead)))
    return due
