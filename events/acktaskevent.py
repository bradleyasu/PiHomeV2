from datetime import datetime, timedelta
import json
from events.pihomeevent import PihomeEvent
from services.taskmanager.taskmanager import TASK_MANAGER, Task, TaskPriority, TaskStatus


class AckTaskEvent(PihomeEvent):
    """
    The AckTask Event will acknowledge any active task/In Progress task in the task manager
    """

    def __init__(self, confirm = True, **kwargs):
        super().__init__()
        self.type = "acktask"
        self.confirm = confirm

    def execute(self):
        id = TASK_MANAGER.ack_task(self.confirm)
        if id is None:
            return {
                "code": 400,
                "body": {"status": "error", "message": "No task to acknowledge"}
            }
        return {
            "code": 200,
            "body": {"status": "success", "message": "Task Acknowledged: {}".format(id)}
        }
    
    def to_json(self):
        return json.dumps({
            "type": self.type,
            "confirm": self.confirm
        })