import json
from events.pihomeevent import PihomeEvent
from services.homeassistant.homeassistant import HOME_ASSISTANT


class HomeAssistantEvent(PihomeEvent):
    type = "homeassistant"
    def __init__(self, entity_id, state = "", data = {}, method = "set", **kwargs):
        super().__init__()
        self.entity_id = entity_id
        self.state = state
        self.data = data
        self.method = method
        if self.entity_id and "." in self.entity_id:
            self.domain = entity_id.split(".")[0]

    def execute(self):

        if self.entity_id is None:
            return {
                "code": 400,
                "body": {"status": "error", "message": "entity_id is required"}
            }
        if self.method != "set" and self.method != "get":
            return {
                "code": 400,
                "body": {"status": "error", "message": "method must be set or get"}
            }
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
                "body": {"status": "success", "message": "Home Assistant Responded", "response": response}
            }
        else:
            return {
                "code": 500,
                "body": {"status": "error", "message": "Error getting response from Home Assistant.  Is Home Assistant configured correctly in PiHome?", "HA_RESP_CODE": response.status_code, "HA_RESP_TEXT": response.text}
            }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "entity_id": self.entity_id,
            "state": self.state,
            "data": self.data,
            "method": self.method
        })

    def to_definition(self):
        return {
            "comment": "Refer to entities in home assistant by their entity_id.  Example: light.living_room_light",
            "type": self.type,
            "entity_id": self.type_def("string"),
            "state": self.type_def("string", False, "State to set the entity to.  Example: turn_on, turn_off"),
            "method": self.type_def("string", True, "Method to use.  Options: set, get"),
            "data": self.type_def("json", False, "JSON data to send to Home Assistant.  Example: {\"brightness\": 255}"),
        }
