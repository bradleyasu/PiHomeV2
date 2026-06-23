"""Calendar screen: month / week / day views over the user's calendars.

Renders from the cache maintained by the always-on calendar_service (which also fires
the approaching-event reminders). The screen itself does no reminder logic — it
reads cached occurrences, draws the current view, and lets the user manage their
calendar list (name + Secret iCal URL) in an in-screen overlay.
"""

from datetime import datetime, date, timedelta

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle

from components.Button.simplebutton import SimpleButton
from components.Keyboard.keyboard import PiTextInput
from interface.pihomescreen import PiHomeScreen
from screens.Calendar import calstore
from screens.Calendar.services.calendar_service import CALENDAR_SERVICE
from theme.theme import Theme
from util.configuration import CONFIG
from util.helpers import toast
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/Calendar/calendar.kv")

_WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
_MONTHS = ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def _hex_rgba(h, a=1.0):
    h = (h or "").lstrip("#")
    if len(h) != 6:
        return [0.30, 0.55, 0.95, a]
    try:
        return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)] + [a]
    except ValueError:
        return [0.30, 0.55, 0.95, a]


def _week_start(d):
    """Sunday on or before d."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _event_date(ev):
    dt = calstore.parse_iso(ev.get("start", ""))
    return dt.date() if dt else None


def _event_time_label(ev):
    if ev.get("all_day"):
        return "all-day"
    dt = calstore.parse_iso(ev.get("start", ""))
    return dt.strftime("%I:%M %p").lstrip("0") if dt else ""


class CalendarScreen(PiHomeScreen):
    """Month/week/day Calendar display."""

    # Defaults derived from the active theme so the first paint matches (screens
    # are lazily created, so startup reload_all() may not have themed this yet);
    # on_config_update() keeps them in sync on later theme changes.
    _th = Theme()
    bg_color      = ColorProperty(_th.get_color(_th.BACKGROUND_PRIMARY))
    header_color  = ColorProperty(_th.get_color(_th.BACKGROUND_SECONDARY))
    card_color    = ColorProperty(_th.get_color(_th.BACKGROUND_SURFACE))
    divider_color = ColorProperty(_th.get_color(_th.BACKGROUND_BORDER))
    text_color    = ColorProperty(_th.get_color(_th.TEXT_PRIMARY))
    muted_color   = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))
    accent_color  = ColorProperty(_th.get_color(_th.ACCENT_PRIMARY))
    status_color  = ColorProperty(_th.get_color(_th.TEXT_SECONDARY))

    current_view = StringProperty("week")   # "day" | "week" | "month"
    period_label = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.anchor = date.today()
        self._manage_overlay = None
        self._name_input = None
        self._url_input = None

    # ── Lifecycle ──

    def _enabled(self):
        """Master switch ([calendar] enabled). Gates both the background service
        and what this screen shows."""
        return CONFIG.get("calendar", "enabled", "1").strip().lower() in ("1", "true")

    def on_enter(self, *args):
        super().on_enter(*args)
        # Re-read base.ini so we reflect setting changes made since the app
        # started. The Settings panel writes the file immediately on toggle, but
        # the live CONFIG is only refreshed when Settings is closed via its own
        # button — navigating here straight from the menu would otherwise show a
        # stale Enabled state until a restart.
        CONFIG.reload()
        self.anchor = date.today()
        CALENDAR_SERVICE.add_listener(self._on_data)
        # Only poke the (disabled-idling) service when the feature is on.
        if self._enabled():
            CALENDAR_SERVICE.request_refresh()
        # Apply the current theme on entry — a lazily-created screen may have
        # missed the startup reload_all(), leaving it on its property defaults.
        super().on_config_update(CONFIG)
        self._render()

    def on_pre_leave(self, *args):
        CALENDAR_SERVICE.remove_listener(self._on_data)
        self._close_manage()
        return super().on_pre_leave(*args)

    def _on_data(self):
        """Service finished a fetch — re-render on the main thread."""
        Clock.schedule_once(lambda dt: self._render(), 0)

    # ── View controls (bound from KV) ──

    def set_view(self, name):
        if name in ("day", "week", "month") and name != self.current_view:
            self.current_view = name
            self._render()

    def go_today(self):
        self.anchor = date.today()
        self._render()

    def shift(self, direction):
        if self.current_view == "day":
            self.anchor += timedelta(days=direction)
        elif self.current_view == "week":
            self.anchor += timedelta(days=7 * direction)
        else:
            self.anchor = self._shift_month(self.anchor, direction)
        self._render()

    @staticmethod
    def _shift_month(d, direction):
        m = d.month - 1 + direction
        year = d.year + m // 12
        month = m % 12 + 1
        return date(year, month, 1)

    # ── Data ──

    def _events_by_date(self, d0, d1):
        """Map date -> list of events (sorted by start) for [d0, d1] inclusive."""
        out = {}
        for ev in calstore.read_events_cache().get("events", []):
            ed = _event_date(ev)
            if ed and d0 <= ed <= d1:
                out.setdefault(ed, []).append(ev)
        for lst in out.values():
            # All-day events first, then timed events by start time.
            lst.sort(key=lambda e: (not e.get("all_day", False), e.get("start", "")))
        return out

    # ── Rendering ──

    def _render(self):
        content = self.ids.get("content")
        if content is None:
            return
        content.clear_widgets()
        if not self._enabled():
            self.period_label = ""
            content.add_widget(self._empty_state(
                "Calendar is disabled.\nEnable it in Settings to show your\ncalendars and reminders."))
            return
        if not calstore.load_calendars():
            self.period_label = ""
            content.add_widget(self._empty_state(
                "No calendars yet.\nTap Manage to add an iCal/ICS URL\n(e.g. a Google Calendar secret address)."))
            return
        if not calstore.AVAILABLE:
            self.period_label = ""
            content.add_widget(self._empty_state(
                "Calendar libraries are installing.\nRestart PiHome to finish setup."))
            return
        if self.current_view == "day":
            self._render_day(content)
        elif self.current_view == "month":
            self._render_month(content)
        else:
            self._render_week(content)

    def _empty_state(self, message):
        # Sized to content (not full-screen) so it never swallows touches.
        box = BoxLayout(orientation="vertical", padding=dp(24))
        lbl = Label(text=message, font_name="Nunito", font_size="15sp",
                    color=self.muted_color, halign="center", valign="middle")
        lbl.bind(size=lambda i, v: setattr(i, "text_size", i.size))
        box.add_widget(lbl)
        return box

    def _chip(self, ev, compact=False):
        """A colored event row/chip."""
        row = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(18) if compact else dp(26), spacing=dp(4),
                        padding=(dp(4), 0, dp(2), 0))
        bar = Widget(size_hint_x=None, width=dp(3))
        with bar.canvas:
            Color(rgba=_hex_rgba(ev.get("color")))
            rect = RoundedRectangle(pos=bar.pos, size=bar.size, radius=[dp(1.5)])
        bar.bind(pos=lambda i, v, r=rect: setattr(r, "pos", i.pos),
                 size=lambda i, v, r=rect: setattr(r, "size", i.size))
        row.add_widget(bar)

        if compact:
            txt = ev.get("title", "")
        else:
            tl = _event_time_label(ev)
            txt = (tl + "  " + ev.get("title", "")).strip()
        lbl = Label(text=txt, font_name="Nunito",
                    font_size="9sp" if compact else "11sp",
                    color=self.text_color, halign="left", valign="middle",
                    shorten=True, shorten_from="right")
        lbl.bind(size=lambda i, v: setattr(i, "text_size", i.size))
        row.add_widget(lbl)
        return row

    # -- Day --

    def _render_day(self, content):
        self.period_label = "{} {}, {}".format(
            _MONTHS[self.anchor.month], self.anchor.day, self.anchor.year)
        events = self._events_by_date(self.anchor, self.anchor).get(self.anchor, [])

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        col = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4),
                        padding=(dp(12), dp(8)))
        col.bind(minimum_height=col.setter("height"))

        wd = _WEEKDAYS[(self.anchor.weekday() + 1) % 7]
        head = Label(text=wd, font_name="Nunito", font_size="12sp", bold=True,
                     color=self.muted_color, size_hint_y=None, height=dp(20),
                     halign="left", valign="middle")
        head.bind(size=lambda i, v: setattr(i, "text_size", i.size))
        col.add_widget(head)

        if not events:
            col.add_widget(self._empty_state("No events"))
        else:
            for ev in events:
                r = self._chip(ev)
                r.height = dp(30)
                col.add_widget(r)

        scroll.add_widget(col)
        content.add_widget(scroll)

    # -- Week --

    def _render_week(self, content):
        start = _week_start(self.anchor)
        end = start + timedelta(days=6)
        self.period_label = "{} {} - {} {}".format(
            _MONTHS[start.month][:3], start.day, _MONTHS[end.month][:3], end.day)
        by_date = self._events_by_date(start, end)
        today = date.today()

        row = BoxLayout(orientation="horizontal", spacing=dp(2), padding=(dp(6), dp(4)))
        for i in range(7):
            d = start + timedelta(days=i)
            col = BoxLayout(orientation="vertical", spacing=dp(2))

            is_today = (d == today)
            hdr = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(30))
            wl = Label(text=_WEEKDAYS[i], font_name="Nunito", font_size="9sp",
                       color=self.accent_color if is_today else self.muted_color,
                       size_hint_y=None, height=dp(13), halign="center", valign="middle")
            wl.bind(size=lambda x, v: setattr(x, "text_size", x.size))
            dl = Label(text=str(d.day), font_name="Nunito", font_size="13sp",
                       bold=is_today,
                       color=self.accent_color if is_today else self.text_color,
                       size_hint_y=None, height=dp(16), halign="center", valign="middle")
            dl.bind(size=lambda x, v: setattr(x, "text_size", x.size))
            hdr.add_widget(wl)
            hdr.add_widget(dl)
            col.add_widget(hdr)

            day_scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
            day_col = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
            day_col.bind(minimum_height=day_col.setter("height"))
            for ev in by_date.get(d, []):
                day_col.add_widget(self._chip(ev, compact=True))
            day_scroll.add_widget(day_col)
            col.add_widget(day_scroll)
            row.add_widget(col)
            if i < 6:
                row.add_widget(self._v_divider())
        content.add_widget(row)

    def _v_divider(self):
        w = Widget(size_hint_x=None, width=dp(1))
        with w.canvas:
            Color(rgba=self.divider_color)
            rect = RoundedRectangle(pos=w.pos, size=w.size)
        w.bind(pos=lambda i, v, r=rect: setattr(r, "pos", i.pos),
               size=lambda i, v, r=rect: setattr(r, "size", i.size))
        return w

    # -- Month --

    def _render_month(self, content):
        first = self.anchor.replace(day=1)
        self.period_label = "{} {}".format(_MONTHS[first.month], first.year)
        grid_start = _week_start(first)
        # 6 weeks covers any month layout.
        grid_end = grid_start + timedelta(days=41)
        by_date = self._events_by_date(grid_start, grid_end)
        today = date.today()

        outer = BoxLayout(orientation="vertical", padding=(dp(6), dp(2)), spacing=dp(1))

        # Weekday header row
        wd_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(16))
        for name in _WEEKDAYS:
            l = Label(text=name, font_name="Nunito", font_size="9sp",
                      color=self.muted_color, halign="center", valign="middle")
            l.bind(size=lambda i, v: setattr(i, "text_size", i.size))
            wd_row.add_widget(l)
        outer.add_widget(wd_row)

        for week in range(6):
            wk = BoxLayout(orientation="horizontal", spacing=dp(2))
            for day in range(7):
                d = grid_start + timedelta(days=week * 7 + day)
                wk.add_widget(self._month_cell(d, d.month == first.month,
                                               d == today, by_date.get(d, [])))
            outer.add_widget(wk)
        content.add_widget(outer)

    def _month_cell(self, d, in_month, is_today, events):
        cell = BoxLayout(orientation="vertical", padding=(dp(3), dp(2)), spacing=dp(1))
        with cell.canvas.before:
            Color(rgba=self.card_color if in_month else self.header_color)
            bg = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[dp(4)])
        cell.bind(pos=lambda i, v, r=bg: setattr(r, "pos", i.pos),
                  size=lambda i, v, r=bg: setattr(r, "size", i.size))

        num = Label(
            text=str(d.day), font_name="Nunito", font_size="10sp", bold=is_today,
            color=self.accent_color if is_today else (
                self.text_color if in_month else self.muted_color),
            size_hint_y=None, height=dp(14), halign="left", valign="middle")
        num.bind(size=lambda i, v: setattr(i, "text_size", i.size))
        cell.add_widget(num)

        shown = 0
        for ev in events:
            if shown >= 3:
                more = Label(text="+{} more".format(len(events) - shown),
                             font_name="Nunito", font_size="8sp", color=self.muted_color,
                             size_hint_y=None, height=dp(11), halign="left", valign="middle")
                more.bind(size=lambda i, v: setattr(i, "text_size", i.size))
                cell.add_widget(more)
                break
            cell.add_widget(self._chip(ev, compact=True))
            shown += 1
        cell.add_widget(Widget())  # push content up
        return cell

    # ── Manage-calendars overlay ──

    def open_manage(self):
        if self._manage_overlay is not None:
            return
        root = self.ids.get("root_float")
        if root is None:
            return

        overlay = BoxLayout(orientation="vertical", size_hint=(None, None),
                            size=(dp(440), dp(330)),
                            pos_hint={"center_x": 0.5, "center_y": 0.5},
                            padding=dp(14), spacing=dp(8))
        with overlay.canvas.before:
            Color(rgba=[0, 0, 0, 0.55])
            shade = RoundedRectangle(pos=(0, 0), size=(dp(10000), dp(10000)))
            Color(rgba=self.card_color[:3] + [1])
            panel = RoundedRectangle(pos=overlay.pos, size=overlay.size, radius=[dp(10)])
        overlay.bind(pos=lambda i, v, r=panel: setattr(r, "pos", i.pos),
                     size=lambda i, v, r=panel: setattr(r, "size", i.size))

        title = Label(text="Manage Calendars", font_name="Nunito", font_size="15sp",
                      bold=True, color=self.text_color, size_hint_y=None, height=dp(24),
                      halign="left", valign="middle")
        title.bind(size=lambda i, v: setattr(i, "text_size", i.size))
        overlay.add_widget(title)

        # Existing calendars list
        list_scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        self._cal_list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self._cal_list.bind(minimum_height=self._cal_list.setter("height"))
        list_scroll.add_widget(self._cal_list)
        overlay.add_widget(list_scroll)

        # Inputs. PiTextInput themes its text/cursor/hint but leaves the
        # background to us — without this it renders as the default white
        # 9-patch (white-on-white in dark mode). Drop the chrome and paint a
        # subtle theme-driven fill, matching screens/Settings.
        fill = list(self.text_color[:3]) + [0.10]
        self._name_input = PiTextInput(hint_text="Calendar name", multiline=False,
                                       size_hint_y=None, height=dp(34))
        self._url_input = PiTextInput(hint_text="Secret iCal URL (.ics)", multiline=False,
                                      secure=True, size_hint_y=None, height=dp(34))
        for ti in (self._name_input, self._url_input):
            ti.background_normal = ""
            ti.background_active = ""
            ti.background_color = fill
            ti.padding = [dp(8), dp(8), dp(8), dp(8)]
        overlay.add_widget(self._name_input)
        overlay.add_widget(self._url_input)

        btns = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36),
                         spacing=dp(8))
        # SimpleButton forces size_hint None,None, so set explicit sizes (else it
        # defaults to the 100x100 Widget size and overlaps the inputs above).
        add_btn = SimpleButton(text="Add", type="primary",
                               size=(dp(200), dp(32)), pos_hint={"center_y": 0.5})
        add_btn.bind(on_release=lambda *a: self._add_calendar())
        close_btn = SimpleButton(text="Close", type="secondary",
                                 size=(dp(200), dp(32)), pos_hint={"center_y": 0.5})
        close_btn.bind(on_release=lambda *a: self._close_manage())
        btns.add_widget(add_btn)
        btns.add_widget(close_btn)
        overlay.add_widget(btns)

        root.add_widget(overlay)
        self._manage_overlay = overlay
        self._rebuild_cal_list()

    def _rebuild_cal_list(self):
        if not getattr(self, "_cal_list", None):
            return
        self._cal_list.clear_widgets()
        cals = calstore.load_calendars()
        if not cals:
            l = Label(text="No calendars added yet", font_name="Nunito", font_size="11sp",
                      color=self.muted_color, size_hint_y=None, height=dp(24))
            self._cal_list.add_widget(l)
            return
        for cal in cals:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30),
                            spacing=dp(6))
            swatch = Widget(size_hint_x=None, width=dp(14))
            with swatch.canvas:
                Color(rgba=_hex_rgba(cal.get("color")))
                rect = RoundedRectangle(pos=swatch.pos, size=(dp(12), dp(12)), radius=[dp(3)])
            swatch.bind(pos=lambda i, v, r=rect: setattr(r, "pos", (i.x, i.center_y - dp(6))),
                        size=lambda i, v, r=rect: setattr(r, "pos", (i.x, i.center_y - dp(6))))
            row.add_widget(swatch)
            name = Label(text=cal.get("name", ""), font_name="Nunito", font_size="12sp",
                         color=self.text_color, halign="left", valign="middle")
            name.bind(size=lambda i, v: setattr(i, "text_size", i.size))
            row.add_widget(name)
            rm = SimpleButton(text="Remove", type="danger",
                              size=(dp(78), dp(26)), pos_hint={"center_y": 0.5})
            rm.bind(on_release=lambda *a, cid=cal.get("id"): self._remove_calendar(cid))
            row.add_widget(rm)
            self._cal_list.add_widget(row)

    def _add_calendar(self):
        name = (self._name_input.text or "").strip() if self._name_input else ""
        url = (self._url_input.text or "").strip() if self._url_input else ""
        if not url:
            toast("Enter a Secret iCal URL", "warning", 3)
            return
        calstore.add_calendar(name or "Calendar", url)
        self._name_input.text = ""
        self._url_input.text = ""
        self._rebuild_cal_list()
        CALENDAR_SERVICE.request_refresh()
        toast("Calendar added", "success", 2)
        self._render()

    def _remove_calendar(self, cid):
        calstore.remove_calendar(cid)
        self._rebuild_cal_list()
        CALENDAR_SERVICE.request_refresh()
        self._render()

    def _close_manage(self):
        if self._manage_overlay is not None:
            root = self.ids.get("root_float")
            if root is not None:
                root.remove_widget(self._manage_overlay)
            self._manage_overlay = None

    # ── Rotary encoder ──

    def on_rotary_turn(self, direction, button_pressed):
        self.shift(direction)
        return True

    def on_rotary_pressed(self):
        order = ["day", "week", "month"]
        self.set_view(order[(order.index(self.current_view) + 1) % 3])
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True

    # ── Theme / settings changes ──

    def on_config_update(self, config):
        super().on_config_update(config)
        # The Enabled switch (and other settings) may have just changed. If the
        # feature is now on and we're visible, kick an immediate fetch so the
        # calendar populates without waiting for the next service tick.
        if self.is_open and self._enabled():
            CALENDAR_SERVICE.request_refresh()
        Clock.schedule_once(lambda dt: self._render(), 0)
