from threading import Thread
import requests
import websockets
import asyncio
import json
from events.pihomeevent import PihomeEventFactory
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER
from kivy.clock import Clock

class HomeAssistant:
    """"
    This class serves as a wrapper for the Home Assistant API.
    """
    PIHOME_CONNECTED_SENSOR = "sensor.pihome_connected"
    ha_is_available = False
    methods = {
        "get": requests.get,
        "post": requests.post,
    }

    current_states = {}
    websocket = None
    
    def __init__(self, **kwargs):
        super(HomeAssistant, self).__init__(**kwargs)

    def __del__(self):
        self.set_state(self.PIHOME_CONNECTED_SENSOR, "off")
        asyncio.get_event_loop().run_until_complete(self.disconnect())

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()

    def connect(self):
        self.configure_connection()

        # this thread will monitor for event changes in home assistant
        self.set_state(self.PIHOME_CONNECTED_SENSOR, "off")
        thread = Thread(target=self._start_loop)
        thread.start()
        self.current_states = self.get_all_states()

    def _start_loop(self):
        loop = asyncio.new_event_loop()
        loop.create_task(self._connect_to_websocket())
        loop.run_forever()

    async def _connect_to_websocket(self):
        socket_url = f"{self.HA_URL}/websocket".replace("http://", "ws://")
        self.websocket = await websockets.connect(socket_url)
        auth = {
            "type": "auth",
            "access_token": self.HA_TOKEN
        }
        response = await self.websocket.recv()
        await self.websocket.send(json.dumps(auth))
        response = await self.websocket.recv()
        PIHOME_LOGGER.info("Home Assistant Connection Response: {}".format(response))
        if "auth_ok" in response:
            message = {
                "id": 1,
                "type": "subscribe_events",
                "event_type": "state_changed"
            }
            await self._send_message(message)
            PIHOME_LOGGER.info("Subscribed to Home Assistant events.")
            self.set_state(self.PIHOME_CONNECTED_SENSOR, "on")
            while True:
                message = await self.websocket.recv()
                data = json.loads(message)
                self._handle_message(data)

    async def _send_message(self, message):
        await self.websocket.send(json.dumps(message))

    def _handle_message(self, data):
        # find and update state in current states
        if "event" in data and "event_type" in data["event"] and data["event"]["event_type"] == "state_changed":
            entity_id = data["event"]["data"]["entity_id"]
            state = data["event"]["data"]["new_state"]
            self.current_states[entity_id] = state
            try:
                PihomeEventFactory.create_event("state_changed", id=entity_id, state=state["state"], data=state).execute()
            except Exception as e:
                PIHOME_LOGGER.error(f"Error processing state change event: {e}")

    def configure_connection(self):
        """
        This function loads the configuration information from the settings file.  If 
        no settings are configured, Home Hassistant will not be available.
        """
        self.HA_URL = CONFIG.get("homeassistant", "host", "http://homeassistant:8123")
        self.HA_TOKEN = CONFIG.get("homeassistant", "token", "")

        # remove trailing slash from url
        if self.HA_URL.endswith("/"):
            self.HA_URL = self.HA_URL[:-1]
        # add /api to the url
        if not self.HA_URL.endswith("/api"):
            self.HA_URL = f"{self.HA_URL}/api"

        self.headers = {
            "Authorization": f"Bearer {self.HA_TOKEN}",
            "content-type": "application/json",
        }

        if self.HA_URL and self.HA_TOKEN:
            self.ha_is_available = True
            PIHOME_LOGGER.info("Home Assistant connection configured.")
        else:
            self.ha_is_available = False
            PIHOME_LOGGER.info("Home Assistant not configured.  Please configure Home Assistant in the settings for this service if you wish to use it.")
            PIHOME_LOGGER.error("{}, {}".format(self.HA_URL, self.HA_TOKEN))
        return self.ha_is_available

    def make_request(self, endpoint, method = "get", data=None):
        """
        Make a request to the Home Assistant API.
        """
        method = self.methods[method.lower()]
        # Construct the URL for the request
        url = f"{self.HA_URL}/{endpoint}"
        # Make the request
        response = method(url, headers=self.headers, json=data)
        # If the request was successful, return the response
        if response.status_code < 300:
            return response
        # Otherwise, raise an exception
        else:
            PIHOME_LOGGER.error(f"Error making request to Home Assistant: {response.text}")
            return response


    def set_state(self, entity_id, state):
        """
        Set the state of an entity in Home Assistant.
        """
        if not self.ha_is_available:
            return None
        data = {
            "state": state
        }
        response = self.make_request(f"states/{entity_id}", method="post", data=data)
        return response

        
    def update_service(self, domain, state, entity_id, data):
        service = f"{domain}/{state}"
        data["entity_id"] = entity_id
        response = self.make_request(f"services/{service}", method="post", data=data)
        return response

    def get_state(self, entity_id):
        """
        Get the state of an entity in Home Assistant.
        """
        if not self.ha_is_available:
            return None
        response = self.make_request(f"states/{entity_id}")
        if response is None:
            return {}
        return response.json()

    def get_all_states(self):
        """
        Get all states from Home Assistant.
        """
        if not self.ha_is_available:
            return {}
        response = self.make_request("states")
        arr = response.json()
        states = {}
        for state in arr:
            states[state["entity_id"]] = state
        return states

    def get_all_lights(self):
        """
        Get the state of all the lights in Home Assistant.
        """
        lights = {}
        for entity_id, state in self.current_states.items():
            if "light" in entity_id:
                lights[entity_id] = state



HOME_ASSISTANT = HomeAssistant()