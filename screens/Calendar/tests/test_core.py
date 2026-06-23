"""Headless unit tests for the Calendar data layer (calstore).

Run from the project root with the venv interpreter:

    venv/bin/python3 screens/Calendar/tests/test_core.py

No display / Kivy needed. Requires icalendar + recurring-ical-events (declared in
the screen manifest's dependencies). Exercises recurrence expansion, timezone
normalization, all-day handling, and the reminder-window + dedup logic.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Make the project root importable (so `screens.Calendar...` resolves).
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from screens.Calendar import calstore  # noqa: E402

_FAILS = []


def check(cond, msg):
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        _FAILS.append(msg)


# A feed with: a one-off timed event, a weekly recurrence, an all-day event,
# and a timed event in a non-local timezone (US/Eastern).
SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:oneoff-1
SUMMARY:One Off Meeting
DTSTART:20260115T150000Z
DTEND:20260115T160000Z
END:VEVENT
BEGIN:VEVENT
UID:weekly-1
SUMMARY:Weekly Standup
DTSTART:20260105T090000Z
DTEND:20260105T093000Z
RRULE:FREQ=WEEKLY;COUNT=10
END:VEVENT
BEGIN:VEVENT
UID:allday-1
SUMMARY:Holiday
DTSTART;VALUE=DATE:20260120
DTEND;VALUE=DATE:20260121
END:VEVENT
BEGIN:VEVENT
UID:tz-1
SUMMARY:Eastern Call
DTSTART;TZID=America/New_York:20260116T100000
DTEND;TZID=America/New_York:20260116T110000
END:VEVENT
END:VCALENDAR
"""


def test_parsing():
    print("test_parsing")
    if not calstore.AVAILABLE:
        print("  SKIP: icalendar/recurring-ical-events not installed")
        _FAILS.append("ICS libs not installed (cannot verify parsing)")
        return

    # Window must span all 10 weekly occurrences (last is ~Mar 9, 2026).
    win_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    win_end = datetime(2026, 4, 1, tzinfo=timezone.utc)
    events = calstore.parse_ics(SAMPLE_ICS, win_start, win_end,
                                calendar_id="c1", calendar_name="Test", color="4C8BF5")

    by_uid = {}
    for e in events:
        by_uid.setdefault(e["uid"], []).append(e)

    check(len(by_uid.get("oneoff-1", [])) == 1, "one-off event appears once")
    check(len(by_uid.get("weekly-1", [])) == 10, "weekly RRULE expands to 10 occurrences (got %d)" % len(by_uid.get("weekly-1", [])))

    allday = by_uid.get("allday-1", [])
    check(len(allday) == 1 and allday[0]["all_day"] is True, "all-day event flagged all_day")

    tz = by_uid.get("tz-1", [])
    check(len(tz) == 1, "tz event present")
    if tz:
        # 10:00 America/New_York on 2026-01-16 == 15:00 UTC. Stored in local tz,
        # but the absolute instant must be preserved.
        start = calstore.parse_iso(tz[0]["start"])
        check(start is not None and start.tzinfo is not None, "tz event start is tz-aware")
        if start:
            utc = start.astimezone(timezone.utc)
            check(utc.hour == 15 and utc.minute == 0,
                  "tz event normalized to correct instant (15:00 UTC, got %02d:%02d)" % (utc.hour, utc.minute))

    check(all(e["color"] == "4C8BF5" and e["calendar_id"] == "c1" for e in events),
          "calendar metadata attached to every occurrence")


def test_reminders():
    print("test_reminders")
    # Event starts 20 minutes from "now"; leads 30 and 10.
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    start = now + timedelta(minutes=20)
    events = [
        {"uid": "e1", "title": "Soon", "all_day": False,
         "start": start.isoformat(), "end": start.isoformat()},
        {"uid": "ad", "title": "AllDay", "all_day": True,
         "start": now.date().isoformat(), "end": now.date().isoformat()},
        {"uid": "past", "title": "Past", "all_day": False,
         "start": (now - timedelta(minutes=5)).isoformat(), "end": now.isoformat()},
    ]

    due = calstore.compute_due(events, now, [30, 10])
    leads = sorted(lead for _, lead, _ in due)
    check(leads == [30], "only the 30-min reminder is due at T-20 (got %s)" % leads)
    check(all(ev["uid"] == "e1" for ev, _, _ in due), "all-day and past events produce no reminders")

    # Ten minutes later (T-10): both 30 and 10 leads are within window.
    later = now + timedelta(minutes=10)
    due2 = calstore.compute_due(events, later, [30, 10])
    leads2 = sorted(lead for _, lead, _ in due2)
    check(leads2 == [10, 30], "both reminders due at T-10 (got %s)" % leads2)

    # Dedup: keys are stable, so a fired-set suppresses re-firing.
    fired = set()
    first = [k for _, _, k in calstore.compute_due(events, now, [30, 10])]
    fired.update(first)
    second = [k for _, _, k in calstore.compute_due(events, now, [30, 10]) if k not in fired]
    check(second == [], "stable keys dedupe a repeated poll")


def test_calendar_list(tmp_suffix="_test"):
    print("test_calendar_list")
    # Redirect the calendar file to a temp path so we don't touch real cache.
    orig = calstore.CALENDARS_FILE
    calstore.CALENDARS_FILE = "cache/calendar_sources%s.json" % tmp_suffix
    try:
        calstore.save_calendars([])
        cid = calstore.add_calendar("Home", "https://example.com/a/basic.ics")
        cals = calstore.load_calendars()
        check(len(cals) == 1 and cals[0]["id"] == cid, "add_calendar persists one entry")
        check(cals[0]["color"], "a palette color was assigned")
        calstore.remove_calendar(cid)
        check(calstore.load_calendars() == [], "remove_calendar empties the list")
    finally:
        try:
            os.remove(calstore.CALENDARS_FILE)
        except OSError:
            pass
        calstore.CALENDARS_FILE = orig


if __name__ == "__main__":
    test_parsing()
    test_reminders()
    test_calendar_list()
    print()
    if _FAILS:
        print("FAILED (%d):" % len(_FAILS))
        for f in _FAILS:
            print("  -", f)
        sys.exit(1)
    print("ALL PASSED")
