"""
DatePicker — generic reusable date spinbox component.

Usage:
    from components.DatePicker.datepicker import DatePicker
    dp_widget = DatePicker()
    dp_widget.get_date()   # → datetime
    dp_widget.set_date(datetime(2026, 3, 15))
"""

from datetime import datetime
import calendar

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from util.phlog import PIHOME_LOGGER

Builder.load_file("./components/DatePicker/datepicker.kv")


class DatePickerColumn(BoxLayout):
    """Single up/value/down spinbox column."""

    col_label     = StringProperty("")
    display_value = StringProperty("01")
    accent_color  = ColorProperty([0.39, 0.71, 1.0,  1.0])
    text_color    = ColorProperty([1.0,  1.0,  1.0,  0.9])
    muted_color   = ColorProperty([1.0,  1.0,  1.0,  0.4])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._value     = 1
        self._min       = 1
        self._max       = 12
        self._fmt       = "{:02d}"
        self._on_change = None

    def configure(self, value, min_val, max_val, fmt="{:02d}", on_change=None):
        self._min       = min_val
        self._max       = max_val
        self._fmt       = fmt
        self._on_change = on_change
        self._set(value)

    def _set(self, v):
        self._value       = max(self._min, min(self._max, v))
        self.display_value = self._fmt.format(self._value)

    def increment(self):
        self._set(self._value + 1 if self._value < self._max else self._min)
        if self._on_change:
            self._on_change()

    def decrement(self):
        self._set(self._value - 1 if self._value > self._min else self._max)
        if self._on_change:
            self._on_change()

    def get_value(self):
        # Parse display_value directly — it's the Kivy property that
        # drives the on-screen label and is updated by _set(), so it
        # is always the true source of what the user sees.
        try:
            return int(self.display_value)
        except ValueError:
            return self._value

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if self.ids.up_btn.collide_point(*touch.pos):
            self.increment()
            return True
        if self.ids.down_btn.collide_point(*touch.pos):
            self.decrement()
            return True
        return False


class DatePicker(BoxLayout):
    """
    Three-column (MM / DD / YYYY) date spinbox.
    Pi-safe: no KV canvas blocks, drawing is minimal (label-only).
    """

    accent_color = ColorProperty([0.39, 0.71, 1.0,  1.0])
    text_color   = ColorProperty([1.0,  1.0,  1.0,  0.9])
    muted_color  = ColorProperty([1.0,  1.0,  1.0,  0.4])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_done = False
        self._pending_date = None
        from kivy.clock import Clock
        Clock.schedule_once(self._init_columns)

    def on_kv_post(self, base_widget):
        # Belt-and-suspenders: also try to init here in case Clock fires late.
        if not self._init_done:
            self._init_columns()

    def _init_columns(self, *args):
        if self._init_done:
            return
        # Guard: ids may not be populated yet if called too early
        if not self.ids:
            from kivy.clock import Clock
            Clock.schedule_once(self._init_columns, 0.05)
            return
        now = datetime.now()
        year_max = now.year + 5

        month_col  = self.ids.month_col
        day_col    = self.ids.day_col
        year_col   = self.ids.year_col
        hour_col   = self.ids.hour_col
        minute_col = self.ids.minute_col

        month_col.configure( now.month+1,  1,        12,       "{:02d}", self._on_month_change)
        day_col.configure(   now.day,    1,        31,       "{:02d}", self._clamp_day)
        year_col.configure(  now.year,   now.year, year_max, "{}",     None)
        hour_col.configure(  now.hour-1,   0,        23,       "{:02d}", None)
        minute_col.configure(now.minute, 0,        59,       "{:02d}", None)
        self._init_done = True
        PIHOME_LOGGER.info("DatePicker: _init_columns completed")

        # Apply any date that was set before we were ready
        if self._pending_date is not None:
            PIHOME_LOGGER.info(f"DatePicker: applying pending date {self._pending_date}")
            self._apply_date(self._pending_date)
            self._pending_date = None

    def _on_month_change(self):
        self._clamp_day()

    def _clamp_day(self):
        """Keep day within the valid range for the current month/year."""
        if not self._init_done:
            return
        m = self.ids.month_col.get_value()
        y = self.ids.year_col.get_value()
        max_day = calendar.monthrange(y, m)[1]
        day_col = self.ids.day_col
        day_col._max = max_day
        if day_col._value > max_day:
            day_col._set(max_day)

    def get_date(self) -> datetime:
        """Return the currently selected date+time as a datetime."""
        # Ensure columns exist even if deferred init hasn't fired yet
        if not self._init_done:
            if self.ids:
                self._init_columns()
            else:
                PIHOME_LOGGER.warn("DatePicker.get_date: ids not ready, returning now()")
                return datetime.now()
        m  = self.ids.month_col.get_value()
        d  = self.ids.day_col.get_value()
        y  = self.ids.year_col.get_value()
        hr = self.ids.hour_col.get_value()
        mn = self.ids.minute_col.get_value()
        PIHOME_LOGGER.info(f"DatePicker.get_date: y={y} m={m} d={d} h={hr} min={mn}")
        try:
            return datetime(y, m, d, hr, mn)
        except ValueError:
            return datetime(y, m, 1, hr, mn)

    def set_date(self, dt: datetime):
        """Set the spinbox to a specific datetime. Safe to call before init."""
        if not self._init_done:
            PIHOME_LOGGER.warn(f"DatePicker.set_date: not init yet, storing pending: {dt}")
            self._pending_date = dt
            return
        self._apply_date(dt)

    def _apply_date(self, dt: datetime):
        """Directly update all column values. Must only be called after init."""
        PIHOME_LOGGER.info(f"DatePicker._apply_date: {dt}")
        year_max = max(dt.year + 5, datetime.now().year + 5)
        month_col  = self.ids.month_col
        day_col    = self.ids.day_col
        year_col   = self.ids.year_col
        hour_col   = self.ids.hour_col
        minute_col = self.ids.minute_col
        year_col._max = year_max
        month_col._set(dt.month)
        year_col._set(dt.year)
        day_col._max = calendar.monthrange(dt.year, dt.month)[1]
        day_col._set(dt.day)
        hour_col._set(dt.hour)
        minute_col._set(dt.minute)
