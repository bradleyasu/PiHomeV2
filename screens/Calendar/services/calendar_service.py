"""Always-on Calendar service.

Polls every configured calendar's Secret iCal feed on a timer (independent of
which screen is open), keeps a rolling window of expanded occurrences cached for
the screen to render, and fires reminder ``AlertEvent`` modals as events approach
(default 30 and 10 minutes before, configurable), each auto-dismissing after a
configurable timeout.

This is a module-level singleton that self-starts a daemon thread in __init__ and
is loaded at boot via util/screen_services.py (manifest "services": ["calendar_service"]).
Both the loader and the screen import this same instance by package path.

Reminders are deduped via a persisted fired-set under cache/, so the same alert
never re-fires across polls or restarts. Degrades quietly when the ICS libraries
aren't installed yet or no calendars are configured.
"""

import os
import threading
from datetime import datetime, timedelta

from kivy.clock import Clock

from screens.Calendar import calstore
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

_STATE_FILE = "cache/calendar_alert_state.json"

# How often the loop wakes to check reminders against the cache. Fetches are
# throttled separately to the (slower) configured fetch interval.
_TICK = 60          # seconds
_WINDOW_BACK = 7    # days of history to keep cached (week-view navigation)
_WINDOW_FWD = 60    # days ahead to expand recurrences for


def _cfg_int(key, default, minimum=None):
    try:
        val = int(CONFIG.get_int("calendar", key, default))
    except (ValueError, TypeError):
        val = default
    if minimum is not None:
        val = max(minimum, val)
    return val


class CalendarService:
    def __init__(self):
        self._stop = threading.Event()
        self._wake = threading.Event()       # lets request_refresh() poke the loop
        self._force_fetch = False
        self._last_fetch = 0.0
        self._state = calstore._load_json(_STATE_FILE, {})   # reminder_key -> fired epoch
        self._listeners = []
        self._thread = threading.Thread(target=self._run, daemon=True, name="calendar-service")
        self._thread.start()

    @property
    def available(self):
        return calstore.AVAILABLE

    # ── Config ──

    def _cfg(self):
        enabled = CONFIG.get("calendar", "enabled", "1").strip().lower() in ("1", "true")
        interval = _cfg_int("fetch_interval", 300, minimum=60)
        lead1 = _cfg_int("alert_lead_1", 30, minimum=0)
        lead2 = _cfg_int("alert_lead_2", 10, minimum=0)
        timeout = _cfg_int("alert_timeout", 10, minimum=1)
        leads = sorted({m for m in (lead1, lead2) if m > 0}, reverse=True)
        return enabled, interval, leads, timeout

    # ── Poll loop ──

    def _run(self):
        # Give the app a moment to finish booting before the first fetch.
        self._stop.wait(8)
        while not self._stop.is_set():
            try:
                # Re-read base.ini each tick so the Enabled switch (and the other
                # settings) take effect without a restart, even if the Settings
                # panel was left via the menu rather than its close button (which
                # is what normally refreshes the live CONFIG).
                CONFIG.reload()
                enabled, interval, leads, timeout = self._cfg()
                if not enabled or not calstore.AVAILABLE or not calstore.load_calendars():
                    self._wait(_TICK)
                    continue

                now = datetime.now().timestamp()
                if self._force_fetch or (now - self._last_fetch) >= interval:
                    self._force_fetch = False
                    self._fetch()

                self._check_reminders(leads, timeout)
            except Exception as e:
                PIHOME_LOGGER.error(f"Calendar service: loop error: {e}")
            self._wait(_TICK)

    def _wait(self, seconds):
        self._wake.wait(seconds)
        self._wake.clear()

    def _fetch(self):
        local_now = datetime.now().astimezone()
        start = local_now - timedelta(days=_WINDOW_BACK)
        end = local_now + timedelta(days=_WINDOW_FWD)
        try:
            calstore.refresh_window(start, end)
            self._last_fetch = datetime.now().timestamp()
            self._notify()
        except Exception as e:
            PIHOME_LOGGER.error(f"Calendar service: fetch failed: {e}")

    # ── Reminders ──

    def _check_reminders(self, leads, timeout_min):
        if not leads:
            return
        events = calstore.read_events_cache().get("events", [])
        now_dt = datetime.now().astimezone()
        changed = False
        for ev, lead, key in calstore.compute_due(events, now_dt, leads):
            if key in self._state:
                continue
            self._fire(ev, lead, timeout_min)
            self._state[key] = now_dt.timestamp()
            changed = True
        if self._prune_state(now_dt):
            changed = True
        if changed:
            calstore._save_json(_STATE_FILE, self._state)

    def _prune_state(self, now_dt):
        """Drop fired keys whose event start is already in the past."""
        cutoff = now_dt.timestamp()
        stale = []
        for key in self._state:
            start_iso = key.split("|")[1] if "|" in key else ""
            start = calstore.parse_iso(start_iso)
            if start is not None and start.timestamp() < cutoff:
                stale.append(key)
        for key in stale:
            self._state.pop(key, None)
        return bool(stale)

    def _fire(self, ev, lead, timeout_min):
        title = ev.get("title", "Event") or "Event"
        msg = self._message(ev, lead)
        PIHOME_LOGGER.info(f"Calendar: reminder '{title}' ({lead} min before)")

        def _do(dt):
            try:
                from events.alertevent import AlertEvent
                from components.Msgbox.msgbox import MSGBOX_TYPES, MSGBOX_BUTTONS
                AlertEvent(
                    title="Reminder: " + title,
                    message=msg,
                    timeout=timeout_min * 60,
                    level=MSGBOX_TYPES["INFO"],
                    buttons=MSGBOX_BUTTONS["OK"],
                ).execute()
            except Exception as e:
                PIHOME_LOGGER.error(f"Calendar: alert failed: {e}")

        Clock.schedule_once(_do, 0)  # AlertEvent touches the UI -> main thread

    @staticmethod
    def _message(ev, lead):
        # ASCII only (Nunito has no en-dash/etc).
        when = ""
        start = calstore.parse_iso(ev.get("start", ""))
        if start is not None:
            when = start.strftime("%I:%M %p").lstrip("0")
        parts = []
        if when:
            parts.append("Starts at {} (in {} min)".format(when, lead))
        else:
            parts.append("Starts in {} min".format(lead))
        loc = (ev.get("location") or "").strip()
        if loc:
            parts.append(loc)
        return "\n".join(parts)

    # ── Snapshot listeners (the screen subscribes to re-render after a fetch) ──

    def add_listener(self, cb):
        if cb not in self._listeners:
            self._listeners.append(cb)

    def remove_listener(self, cb):
        if cb in self._listeners:
            self._listeners.remove(cb)

    def _notify(self):
        for cb in list(self._listeners):
            Clock.schedule_once(lambda dt, c=cb: self._safe_cb(c), 0)

    def _safe_cb(self, cb):
        try:
            cb()
        except Exception as e:
            PIHOME_LOGGER.error(f"Calendar listener error: {e}")

    def request_refresh(self):
        """Ask the loop to fetch as soon as possible (called by the screen)."""
        self._force_fetch = True
        self._wake.set()

    def shutdown(self):
        self._stop.set()
        self._wake.set()


CALENDAR_SERVICE = CalendarService()
