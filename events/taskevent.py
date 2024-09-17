from datetime import datetime, timedelta
import json
from events.pihomeevent import PihomeEvent
from services.taskmanager.taskmanager import TASK_MANAGER, EventTask, ScheduledTask, Task, TaskPriority, TaskStatus


class TaskEvent(PihomeEvent):
    type = "task"
    
    def __init__(self, 
                 name, 
                 description, 
                 priority, 
                 start_time = None, 
                 state_id = None,
                 trigger_state = None,
                 is_passive = False, 
                 repeat_days = 0, 
                 on_run = None, 
                 on_confirm = None, 
                 on_cancel = None, 
                 background_image = None, 
                 **kwargs):
        super().__init__()
        self.cacheable = True
        self.name = name
        self.description = description
        self.start_time = self.str_to_date(start_time)
        self.state_id = state_id
        self.trigger_state = trigger_state
        self.status = TaskStatus.PENDING
        # set self.priority to the priority enum
        self.priority = TaskPriority(priority) if priority != None else TaskPriority(1)
        self.repeat_days = repeat_days
        self.on_run = on_run
        self.is_passive = is_passive
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.background_image = background_image

    def str_to_date(self, date_str):
        if date_str == None:
            return datetime.now()
        if date_str.startswith("delta:"):
            # Example input could be "delta:1 days" or "delta:1 hours"
            delta = date_str.split(":")[1]
            delta = delta.split(" ")
            # If delta[1] doesn't end with an s, add it
            if not delta[1].endswith("s"):
                delta[1] += "s"
            self.cacheable = False
            return datetime.now() + timedelta(**{delta[1]: int(delta[0])})
            
        return datetime.strptime(date_str, "%m/%d/%Y %H:%M")

    def is_expired(self):
        return self.start_time <= datetime.now()

    def execute(self):
        task = None
        if self.state_id is None:
            task = ScheduledTask(self.name, self.description, self.start_time, self.status, self.priority, self.is_passive, self.repeat_days, self.on_run, self.on_confirm, self.on_cancel, self.background_image, self.cacheable)
            if self.is_expired():
                return {
                    "code": 400,
                    "body": {"status": "error", "message": "Task is expired"}
                }
        else:
            task = EventTask(self.name, self.description, self.state_id, self.trigger_state, self.status, self.priority, self.is_passive, self.on_run, self.on_confirm, self.on_cancel, self.background_image, self.cacheable)

        if task is not None:
            TASK_MANAGER.add_task(task)
        else:
            return {
                "code": 500,
                "body": {"status": "error", "message": "Failed to create task.  Could not identify task type."}
            }
        return {
            "code": 200,
            "body": {"status": "success", "message": "Task added", "task_id": task.id}
        }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "start_time": self.start_time,
            "state_id": self.state_id,
            "trigger_state": self.trigger_state,
            "status": self.status,
            "priority": self.priority,
            "repeat_days": self.repeat_days,
            "on_run": self.on_run,
            "on_confirm": self.on_confirm,
            "on_cancel": self.on_cancel
        })

    def to_definition(self):
        return {
            "comment": "Tasks can be scheduled to run at a specific time or triggered by a state change. A state_id OR start_time must be provided, but not both.",
            "type": self.type,
            "name": self.type_def("string"),
            "description": self.type_def("string"),
            "start_time": self.type_def("string", False),
            "state_id": self.type_def("string", False),
            "trigger_state": self.type_def("string", False),
            "status": self.type_def("string"),
            "priority": self.type_def("integer", True, "1 = Low, 2 = Medium, 3 = High"),
            "repeat_days": self.type_def("integer", False),
            "on_run": self.type_def("event", False),
            "on_confirm": self.type_def("event", False),
            "on_cancel": self.type_def("event", False)
        }
