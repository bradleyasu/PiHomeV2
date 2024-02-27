

import json
from events.pihomeevent import PihomeEvent
from services.taskmanager.taskmanager import TASK_MANAGER


class DeleteEvent(PihomeEvent):
    type = "delete"
    def __init__(self, entity, id, **kwargs):
        super().__init__()
        self.entity = entity
        self.id = id

    def execute(self):
        switcher = {
            "task": TASK_MANAGER.remove_task_by_id
        }
        if self.entity in switcher:
            if switcher[self.entity](self.id):
                return {
                    "code": 200,
                    "body": {"status": "success", "message": "Entity deleted successfully"}
                }
            else: 
                return {
                    "code": 404,
                    "body": {"status": "error", "message": "Entity not found"}
                }
        else:
            return {
                "code": 400,
                "body": {"status": "error", "message": "Invalid entity", "valid_entities": list(switcher.keys())}
            }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "entity": self.entity,
            "id": self.id
        })
    

    def to_definition(self):
        return {
            "type": self.type,
            "entity": self.type_def("string"),
            "id": self.type_def("string")
        }