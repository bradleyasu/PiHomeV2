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

    def _entity_options(self):
        """Build an {entity_id: friendly_name} map from Home Assistant's cached
        states, sorted by the human-readable label.

        The event-builder UI renders a dict-valued `options` field as a Select
        where the dict key is the submitted value (entity_id) and the dict value
        is the displayed label (friendly name).  Returns an empty dict if HA has
        no states available (e.g. not configured / not yet connected)."""
        states = HOME_ASSISTANT.current_states or {}
        # If the cache is empty but HA is configured, try a one-off live fetch
        # so the dropdown is populated even right after startup.
        if not states and getattr(HOME_ASSISTANT, "ha_is_available", False):
            try:
                states = HOME_ASSISTANT.get_all_states() or {}
            except Exception:
                states = {}

        options = {}
        for entity_id, st in states.items():
            label = entity_id
            if isinstance(st, dict):
                label = st.get("attributes", {}).get("friendly_name") or entity_id
            options[entity_id] = label

        # Sort by label (case-insensitive) for a usable dropdown.
        return dict(sorted(options.items(), key=lambda kv: kv[1].lower()))

    def to_definition(self):
        entity_options = self._entity_options()
        if entity_options:
            entity_field = self.type_def("option", True, "Entity to target", entity_options)
        else:
            # Fall back to free-text entry when no entities are cached, so the
            # event can still be built while HA is offline.
            entity_field = self.type_def("string", True, "Entity to target.  Example: light.living_room_light")

        return {
            "type": self.type,
            "entity_id": entity_field,
            "state": self.type_def("string", False, "State to set the entity to.  Example: turn_on, turn_off"),
            "method": self.type_def("option", True, "Method to use: 'set' to call a service, 'get' to read state", ["set", "get"]),
            "data": self.type_def("json", False, "JSON data to send to Home Assistant.  Example: {\"brightness\": 255}"),
        }
