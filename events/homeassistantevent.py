import json
from events.pihomeevent import PihomeEvent
from services.homeassistant.homeassistant import HOME_ASSISTANT


class HomeAssistantEvent(PihomeEvent):
    type = "homeassistant"
    def __init__(self, entity_id, state, data = {}, method = "set", **kwargs):
        super().__init__()
        self.entity_id = entity_id
        self.domain = entity_id.split(".")[0]
        self.state = state
        self.data = data
        self.method = method

    def execute(self):

        # try to convert self.data to a dictionary
        try:
            self.data = json.loads(self.data)
        except:
            print("Error converting state to dictionary")

        if self.method == "set":
            response = HOME_ASSISTANT.update_service(self.domain, self.state, self.entity_id, self.data)
        elif self.method == "get":
            response = HOME_ASSISTANT.get_state(self.entity_id)

        if response:
            # if response is not json, make it json
            if self.method == "set":
                response = response.json()
            return {
                "code": 200,
                "body": {"status": "success", "message": "State set in Home Assistant", "response": response}
            }
        else:
            return {
                "code": 500,
                "body": {"status": "error", "message": "Error setting state in Home Assistant.  Is Home Assistant configured correctly in PiHome?"}
            }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "label": self.label,
            "level": self.level,
            "timeout": self.timeout
        })
