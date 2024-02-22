from datetime import datetime
import json
from components.Msgbox.msgbox import MSGBOX_FACTORY
from events.pihomeevent import PihomeEvent
from services.taskmanager.taskmanager import TASK_MANAGER, Task, TaskPriority, TaskStatus


class TaskEvent(PihomeEvent):
    def __init__(self, name, description, start_time, priority, repeat_days = 0, task_function = None, on_confirm = None, on_cancel = None, **kwargs):
        super().__init__()
        self.type = "task"
        self.name = name
        self.description = description
        self.start_time = self.str_to_date(start_time)
        self.status = TaskStatus.PENDING
        # set self.priority to the priority enum
        self.priority = TaskPriority(priority)
        self.repeat_days = repeat_days
        self.task_function = task_function
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

    def str_to_date(self, date_str):
        return datetime.strptime(date_str, "%m/%d/%Y %H:%M")

    def is_expired(self):
        return self.start_time <= datetime.now()

    def execute(self):
        if self.is_expired():
            return {
                "code": 400,
                "body": {"status": "error", "message": "Task is expired"}
            }
        task = Task(self.name, self.description, self.start_time, self.status, self.priority, self.repeat_days, self.task_function, self.on_confirm, self.on_cancel)
        TASK_MANAGER.add_task(task)
        return {
            "code": 200,
            "body": {"status": "success", "message": "Task added"}
        }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "start_time": self.start_time,
            "status": self.status,
            "priority": self.priority,
            "repeat_days": self.repeat_days,
            "task_function": self.task_function,
            "on_confirm": self.on_confirm,
            "on_cancel": self.on_cancel
        })
