from datetime import datetime, timedelta

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ColorProperty, NumericProperty

from interface.pihomescreen import PiHomeScreen
from screens.TaskManagerScreen.taskrow import TaskRow
from services.taskmanager.taskmanager import TASK_MANAGER, TaskPriority, TaskStatus
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/TaskManagerScreen/TaskManagerScreen.kv")

# ── Constants ──────────────────────────────────────────────────────────────────

_PRIORITY_COLORS = {
    TaskPriority.LOW:    [0.39, 0.71, 1.00, 1.0],
    TaskPriority.MEDIUM: [1.00, 0.60, 0.20, 1.0],
    TaskPriority.HIGH:   [1.00, 0.28, 0.28, 1.0],
}

_DUE_PRESETS = [
    ("15m",   timedelta(minutes=15)),
    ("30m",   timedelta(minutes=30)),
    ("1h",    timedelta(hours=1)),
    ("2h",    timedelta(hours=2)),
    ("4h",    timedelta(hours=4)),
    ("1 day", timedelta(days=1)),
]

# ── Panel heights (dp values — must match KV row heights) ──────────────────
# Due-in mode:  header 48 + name 48 + desc 44 + priority 42
#               + toggle row 40 + due-in chips 42 + create btn 54  = 318
# Date mode:    same base − chips 42 + date picker 96 + repeat 48  = 420
_PANEL_HEIGHT_DUE_IN = 318
_PANEL_HEIGHT_DATE   = 420


class TaskManagerScreen(PiHomeScreen):
    """Browse, create and delete scheduled tasks."""

    bg_color     = ColorProperty([0.08, 0.10, 0.14, 1.0])
    header_color = ColorProperty([0.10, 0.13, 0.18, 1.0])
    card_color   = ColorProperty([0.11, 0.14, 0.20, 1.0])
    text_color   = ColorProperty([1.0,  1.0,  1.0,  0.90])
    muted_color  = ColorProperty([1.0,  1.0,  1.0,  0.40])
    accent_color = ColorProperty([0.39, 0.71, 1.00, 1.0])
    task_count   = NumericProperty(0)

    _panel_open    = False
    _panel_closing  = False   # True while the hide animation is running
    _date_mode     = False       # False = due-in presets, True = specific date
    _switching     = False       # suppresses toggle handler during panel reset
    _selected_prio = 2          # MEDIUM default
    _selected_due  = 2          # "1h" default (index into _DUE_PRESETS)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from kivy.clock import Clock as _Clock
        _Clock.schedule_once(self._bind_switch)

    def _bind_switch(self, *args):
        self.ids.date_mode_switch.bind(
            enabled=lambda sw, v: self.on_date_mode_toggle(v)
        )
        # Bind create button directly on the widget — avoids coordinate
        # conversion issues when checking collide_point at the Screen level.
        self.ids.create_btn.bind(on_touch_up=self._on_create_btn_touch)

    def _on_create_btn_touch(self, widget, touch):
        """Direct handler bound on the create_btn label."""
        if widget.collide_point(*touch.pos):
            if self._panel_open:
                self.submit_create()
                return True
        return False

    # ── Screen lifecycle ───────────────────────────────────────────────────────

    def on_enter(self, *args):
        super().on_enter(*args)
        self.refresh_tasks()

    # ── Task list ──────────────────────────────────────────────────────────────

    def refresh_tasks(self):
        scroll = self.ids.task_scroll
        scroll.clear_widgets()

        tasks = TASK_MANAGER.get_tasks()

        def _sort_key(t):
            active = t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELED)
            st = getattr(t, 'start_time', datetime.max)
            return (not active, st)

        sorted_tasks = sorted(tasks, key=_sort_key)

        active_count = sum(
            1 for t in tasks
            if t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELED)
        )
        self.task_count = active_count

        empty = self.ids.empty_state
        empty.opacity = 0 if sorted_tasks else 1

        for task in sorted_tasks:
            scroll.add_widget(self._make_row(task))

    def _make_row(self, task):
        prio_color = _PRIORITY_COLORS.get(task.priority, _PRIORITY_COLORS[TaskPriority.LOW])

        # Due-time display
        start_time = getattr(task, 'start_time', None)
        PIHOME_LOGGER.info(f"TaskManagerScreen._make_row: task={task.name!r} start_time={start_time!r}")
        if start_time:
            diff = start_time - datetime.now()
            secs = diff.total_seconds()
            PIHOME_LOGGER.info(f"TaskManagerScreen._make_row: secs={secs:.1f} for task={task.name!r}")
            if secs < 0:
                due_str = "overdue"
            elif secs < 3600:
                mins = max(1, int(secs / 60))
                due_str = f"in {mins} min"
            elif secs < 86400:
                hrs  = int(secs / 3600)
                mins = int((secs % 3600) / 60)
                due_str = f"in {hrs}h {mins}m" if mins else f"in {hrs}h"
            elif secs < 7 * 86400:
                days = int(secs / 86400)
                due_str = f"in {days} day" if days == 1 else f"in {days} days"
            elif secs < 30 * 86400:
                weeks = int(secs / (7 * 86400))
                due_str = f"in {weeks} week" if weeks == 1 else f"in {weeks} weeks"
            elif secs < 365 * 86400:
                months = int(secs / (30 * 86400))
                due_str = f"in {months} month" if months == 1 else f"in {months} months"
            else:
                years = int(secs / (365 * 86400))
                due_str = f"in {years} year" if years == 1 else f"in {years} years"
        else:
            due_str = "event-based"

        # Dim finished rows
        is_done = task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELED)
        alpha      = 0.40 if is_done else 0.90
        muted_a    = 0.20 if is_done else 0.40
        accent_a   = 0.30 if is_done else 1.0

        row = TaskRow(
            task_id          = task.id,
            task_name        = task.name,
            task_description = task.description or "",
            due_label        = due_str,
            priority_color   = prio_color,
            text_color       = [1, 1, 1, alpha],
            muted_color      = [1, 1, 1, muted_a],
            accent_color     = prio_color[:3] + [accent_a],
        )
        # Set callback directly — avoids Kivy's on_* kwarg routing as event binding
        row.on_delete_cb = self._delete_task
        return row

    def _delete_task(self, task_id):
        TASK_MANAGER.remove_task_by_id(task_id)
        self.refresh_tasks()

    # ── Date mode toggle ──────────────────────────────────────────────────────

    def on_date_mode_toggle(self, enabled):
        """Called by PiHomeSwitch.on_change."""
        self._date_mode = enabled
        self._update_toggle_labels(enabled)
        from kivy.metrics import dp
        if enabled:
            # Hide chips, show date section
            Animation(height=0, opacity=0, duration=0.15, t='in_cubic').start(
                self.ids.due_in_row)
            target_sec = dp(96 + 48)  # date picker + repeat row
            Animation(height=target_sec, opacity=1, duration=0.2, t='out_cubic').start(
                self.ids.specific_date_section)
            # Grow panel
            Animation(
                height=dp(_PANEL_HEIGHT_DATE), duration=0.2, t='out_cubic'
            ).start(self.ids.create_panel)
        else:
            # Show chips, hide date section
            Animation(
                height=dp(42), opacity=1, duration=0.2, t='out_cubic'
            ).start(self.ids.due_in_row)
            Animation(height=0, opacity=0, duration=0.15, t='in_cubic').start(
                self.ids.specific_date_section)
            # Shrink panel
            Animation(
                height=dp(_PANEL_HEIGHT_DUE_IN), duration=0.2, t='out_cubic'
            ).start(self.ids.create_panel)

    def _update_toggle_labels(self, date_mode):
        lbl_in = self.ids.lbl_due_in
        lbl_sp = self.ids.lbl_specific
        if date_mode:
            lbl_in.color  = self.muted_color[:3] + [0.45]
            lbl_in.bold   = False
            lbl_sp.color  = self.accent_color
            lbl_sp.bold   = True
        else:
            lbl_in.color  = self.accent_color
            lbl_in.bold   = True
            lbl_sp.color  = self.muted_color[:3] + [0.45]
            lbl_sp.bold   = False

    # ── Priority / due-in selectors ───────────────────────────────────────────

    def toggle_create_panel(self):
        if self._panel_open:
            self.hide_create_panel()
        else:
            self.show_create_panel()

    def show_create_panel(self):
        self._panel_open = True
        from kivy.metrics import dp
        panel = self.ids.create_panel

        # Reset form to defaults
        self.ids.name_input.text = ""
        self.ids.desc_input.text = ""
        self._select_priority(2)
        self._select_due(2)

        # Always open in due-in mode
        self._switching = True
        self._date_mode = False
        sw = self.ids.date_mode_switch
        if sw.enabled:
            sw.enabled = False
        self._switching = False
        self.ids.due_in_row.height      = dp(42)
        self.ids.due_in_row.opacity     = 1
        specific = self.ids.specific_date_section
        specific.height  = 0
        specific.opacity = 0
        self._update_toggle_labels(False)

        # Reset date picker to current time — user can adjust from here
        from datetime import datetime, timedelta as _td
        self.ids.date_picker.set_date(datetime.now())
        self.ids.repeat_stepper.value = 0

        target_h = dp(_PANEL_HEIGHT_DUE_IN)
        anim = Animation(height=target_h, opacity=1,
                         duration=0.25, transition='out_cubic')
        anim.start(panel)

    def hide_create_panel(self):
        self._panel_open   = False
        self._panel_closing = True
        panel = self.ids.create_panel
        anim = Animation(height=0, opacity=0,
                         duration=0.18, transition='in_cubic')
        anim.bind(on_complete=self._on_panel_hidden)
        anim.start(panel)

    def _on_panel_hidden(self, *args):
        self._panel_closing = False

    def _select_priority(self, value):
        """Highlight the chosen priority pill (1=LOW, 2=MEDIUM, 3=HIGH)."""
        self._selected_prio = value
        pill_colors = {
            1: [0.39, 0.71, 1.00, 1.0],
            2: [1.00, 0.60, 0.20, 1.0],
            3: [1.00, 0.28, 0.28, 1.0],
        }
        for p, lbl_id in [(1, 'prio_low'), (2, 'prio_med'), (3, 'prio_high')]:
            lbl = self.ids[lbl_id]
            if p == value:
                lbl.color = pill_colors[p]
                lbl.bold  = True
            else:
                lbl.color = [1, 1, 1, 0.30]
                lbl.bold  = False

    def _select_due(self, index):
        """Highlight the chosen due-in preset."""
        self._selected_due = index
        for i, lbl_id in enumerate(['due_0', 'due_1', 'due_2', 'due_3', 'due_4', 'due_5']):
            lbl = self.ids[lbl_id]
            if i == index:
                lbl.color = self.accent_color
                lbl.bold  = True
            else:
                lbl.color = [1, 1, 1, 0.30]
                lbl.bold  = False

    def submit_create(self):
        name = self.ids.name_input.text.strip()
        if not name:
            PIHOME_LOGGER.warn("TaskManagerScreen: create attempted with empty name")
            return

        desc  = self.ids.desc_input.text.strip()
        prio  = self._selected_prio

        try:
            if self._date_mode:
                chosen_date = self.ids.date_picker.get_date()
                PIHOME_LOGGER.info(f"TaskManagerScreen: date picker returned {chosen_date}")
                # TaskEvent.execute() rejects anything where start_time <= now.
                # Ensure the chosen time is at least 1 minute in the future.
                min_future = datetime.now() + timedelta(minutes=1)
                if chosen_date <= datetime.now():
                    chosen_date = min_future
                    PIHOME_LOGGER.warn(
                        "TaskManagerScreen: chosen datetime was in the past, "
                        "nudged to 1 minute from now"
                    )
                start = chosen_date.strftime("%m/%d/%Y %H:%M")
                PIHOME_LOGGER.info(f"TaskManagerScreen: create with start_time={start}")
                repeat_days = int(self.ids.repeat_stepper.value)
            else:
                offset = _DUE_PRESETS[self._selected_due][1]
                start  = (datetime.now() + offset).strftime("%m/%d/%Y %H:%M")
                repeat_days = 0
                PIHOME_LOGGER.info(f"TaskManagerScreen: due-in create with start_time={start}")

            from events.taskevent import TaskEvent
            result = TaskEvent(
                name        = name,
                description = desc,
                priority    = prio,
                start_time  = start,
                repeat_days = repeat_days,
            ).execute()
            PIHOME_LOGGER.info(f"TaskManagerScreen: create result = {result}")

            if result and result.get("code") != 200:
                PIHOME_LOGGER.error(
                    f"TaskManagerScreen: task not created — {result.get('body')}"
                )
                return

        except Exception as e:
            PIHOME_LOGGER.error(f"TaskManagerScreen: create failed — {e}")
            return

        self.hide_create_panel()
        Clock.schedule_once(lambda dt: self.refresh_tasks(), 0.3)

    # ── Touch handling ─────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        # Block touches while the panel is open OR still animating closed.
        # Use the panel's actual height as the ground truth — not the flag
        # which goes False before the animation finishes.
        panel = self.ids.create_panel
        if (self._panel_open or self._panel_closing) and panel.height > 0:
            if panel.collide_point(*touch.pos):
                touch.grab(self)
            # Either way, eat the touch — don't let children see it at all.
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        # Kivy delivers on_touch_up twice for a grabbed touch:
        #   1) with touch.grab_current is self  → our intentional grab
        #   2) with touch.grab_current = None   → normal tree dispatch
        # We must block BOTH paths while the panel is open or closing.
        panel = self.ids.create_panel
        panel_active = (self._panel_open or self._panel_closing) and panel.height > 0

        if touch.grab_current is self:
            touch.ungrab(self)
            if self.ids.add_btn.collide_point(*touch.pos):
                self.toggle_create_panel()
                return True
            if self._panel_open:
                if self.ids.close_panel_btn.collide_point(*touch.pos):
                    self.hide_create_panel()
                    return True
                for p, lbl_id in [(1, 'prio_low'), (2, 'prio_med'), (3, 'prio_high')]:
                    if self.ids[lbl_id].collide_point(*touch.pos):
                        self._select_priority(p)
                        return True
                for i, lbl_id in enumerate(['due_0', 'due_1', 'due_2', 'due_3', 'due_4', 'due_5']):
                    if self.ids[lbl_id].collide_point(*touch.pos):
                        self._select_due(i)
                        return True
            return True  # swallow — panel was open

        # Second delivery (normal tree dispatch): block children if panel active.
        if panel_active:
            return True

        if not self.collide_point(*touch.pos):
            return super().on_touch_up(touch)

        # Panel is fully closed — handle add button.
        if self.ids.add_btn.collide_point(*touch.pos):
            self.toggle_create_panel()
            return True

        return super().on_touch_up(touch)
