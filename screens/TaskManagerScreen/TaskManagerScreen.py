from datetime import datetime, timedelta

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ColorProperty, NumericProperty

from interface.pihomescreen import PiHomeScreen
from screens.TaskManagerScreen.taskrow import TaskRow
from services.taskmanager.taskmanager import TASK_MANAGER, TaskPriority, TaskStatus

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

_PANEL_HEIGHT = 278   # dp — sum of all panel rows


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
    _selected_prio = 2          # MEDIUM default
    _selected_due  = 2          # "1h" default (index into _DUE_PRESETS)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
        if start_time:
            diff = start_time - datetime.now()
            secs = diff.total_seconds()
            if secs < 0:
                due_str = "overdue"
            elif secs < 3600:
                due_str = f"in {int(secs / 60)}m"
            elif secs < 86400:
                hrs = int(secs / 3600)
                due_str = f"in {hrs}h"
            else:
                due_str = start_time.strftime("%m/%d  %H:%M")
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
            on_delete        = self._delete_task,
        )
        return row

    def _delete_task(self, task_id):
        TASK_MANAGER.remove_task_by_id(task_id)
        self.refresh_tasks()

    # ── Create panel ──────────────────────────────────────────────────────────

    def toggle_create_panel(self):
        if self._panel_open:
            self.hide_create_panel()
        else:
            self.show_create_panel()

    def show_create_panel(self):
        self._panel_open = True
        from kivy.metrics import dp
        panel = self.ids.create_panel
        anim = Animation(height=dp(_PANEL_HEIGHT), opacity=1,
                         duration=0.25, transition='out_cubic')
        anim.start(panel)

        # Reset form to defaults
        self.ids.name_input.text = ""
        self.ids.desc_input.text = ""
        self._select_priority(2)
        self._select_due(2)

    def hide_create_panel(self):
        self._panel_open = False
        panel = self.ids.create_panel
        anim = Animation(height=0, opacity=0,
                         duration=0.18, transition='in_cubic')
        anim.start(panel)

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
            return

        desc   = self.ids.desc_input.text.strip()
        offset = _DUE_PRESETS[self._selected_due][1]
        start  = (datetime.now() + offset).strftime("%m/%d/%Y %H:%M")
        prio   = self._selected_prio

        from events.taskevent import TaskEvent
        TaskEvent(
            name        = name,
            description = desc,
            priority    = prio,
            start_time  = start,
        ).execute()

        self.hide_create_panel()
        Clock.schedule_once(lambda dt: self.refresh_tasks(), 0.25)

    # ── Touch handling ─────────────────────────────────────────────────────────

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_up(touch)

        # Add / toggle panel button
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

            if self.ids.create_btn.collide_point(*touch.pos):
                self.submit_create()
                return True

        return super().on_touch_up(touch)
