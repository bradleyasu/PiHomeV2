'''
This event is more of an internal event that is used to trigger other events.  It is not meant to be used directly.
It is used when PiHome events need to trigger some state change event, for example, Home Assistant events.
'''


import json
from events.pihomeevent import PihomeEvent


class StateChangeEvent(PihomeEvent):
    type = "state_changed"
    def __init__(self, id, state = "", data = {}, **kwargs):
        super().__init__()
        self.id = id
        self.state = state
        self.data = data

    def execute(self):
        '''
        Notify anything that should be listening to state change events
        '''
        # Notify TaskManager
        from services.taskmanager.taskmanager import TASK_MANAGER
        TASK_MANAGER.notify_state_change(self.id, self.state)

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "id": self.id,
            "state": self.state,
            "data": self.data
        })

    def to_definition(self):
        return {
            "comment": "Internal State Event. Not meant to be used directly, unless you are testing.",
            "type": self.type,
            "id": self.type_def("string"),
            "state": self.type_def("string", False, "updated state"),
            "data": self.type_def("object", False, "additional data")
        }
