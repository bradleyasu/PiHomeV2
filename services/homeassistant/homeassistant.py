from threading import Thread
import atexit
import json
import os
import uuid
import requests
import websockets
import asyncio
from events.pihomeevent import PihomeEventFactory
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER
from kivy.clock import Clock

class HaReactListener:
    """A persistent HA state-change listener that fires a PiHome event as
    its action.  Serialised to / from ha_listeners.pihome as plain JSON."""

    def __init__(self, entity_id, action, state=None, id=None):
        self.id        = id or str(uuid.uuid4())
        self.entity_id = entity_id
        self.state     = state   # None = fire on ANY state change
        self.action    = action  # dict — executed via PihomeEventFactory

    def matches(self, entity_id, new_state):
        if self.entity_id != entity_id:
            return False
        if self.state is None:
            return True
        return self.state == new_state

    def to_dict(self):
        return {
            "id":        self.id,
            "entity_id": self.entity_id,
            "state":     self.state,
            "action":    self.action,
        }

    @staticmethod
    def from_dict(d):
        return HaReactListener(
            entity_id = d["entity_id"],
            action    = d["action"],
            state     = d.get("state"),
            id        = d["id"],
        )


class HomeAssistant:
    """"
    This class serves as a wrapper for the Home Assistant API.
    """
    PIHOME_CONNECTED_SENSOR = "sensor.pihome_connected"
    REACT_LISTENERS_FILE    = "ha_listeners.pihome"
    ha_is_available = False
    methods = {
        "get": requests.get,
        "post": requests.post,
    }

    current_states = {}
    websocket = None
    listeners = []
    ha_react_listeners = []
    event_thread = None
    event_loop = None
    is_shutting_down = False

    def __init__(self, **kwargs):
        super(HomeAssistant, self).__init__(**kwargs)
        self.ha_react_listeners = []  # instance list — avoids class-level sharing
        atexit.register(self._serialize_react_listeners)

    def __del__(self):
        self.shutdown()

    def shutdown(self):
        """Immediately shutdown Home Assistant connection"""
        if self.is_shutting_down:
            return
        
        PIHOME_LOGGER.info("Home Assistant: Shutting down...")
        self.is_shutting_down = True
        
        try:
            self.set_state(self.PIHOME_CONNECTED_SENSOR, "off")
        except:
            pass
        
        # Stop the event loop immediately
        if self.event_loop and self.event_loop.is_running():
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()

    def connect(self):
        try:
            self.configure_connection()

            # this thread will monitor for event changes in home assistant
            self.set_state(self.PIHOME_CONNECTED_SENSOR, "off")
            self.event_thread = Thread(target=self._start_loop, daemon=True)
            self.event_thread.start()
            self.current_states = self.get_all_states()
            self._deserialize_react_listeners()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error connecting to Home Assistant: {e}")
            self.ha_is_available = False
            return False

    def _start_loop(self):
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.create_task(self._connect_to_websocket())
        try:
            self.event_loop.run_forever()
        finally:
            self.event_loop.close()

    async def _connect_to_websocket(self):
        backoff = 1  # seconds
        max_backoff = 60

        while not self.is_shutting_down:
            try:
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
                if "auth_ok" not in response:
                    PIHOME_LOGGER.error("Home Assistant authentication failed.")
                    break

                message = {
                    "id": 1,
                    "type": "subscribe_events",
                    "event_type": "state_changed"
                }
                await self._send_message(message)
                PIHOME_LOGGER.info("Subscribed to Home Assistant events.")
                self.set_state(self.PIHOME_CONNECTED_SENSOR, "on")
                self.current_states = self.get_all_states()
                backoff = 1  # reset backoff on successful connection

                while not self.is_shutting_down:
                    message = await self.websocket.recv()
                    data = json.loads(message)
                    self._handle_message(data)

            except Exception as e:
                if self.is_shutting_down:
                    break
                PIHOME_LOGGER.error(f"WebSocket error: {e}")
                self.set_state(self.PIHOME_CONNECTED_SENSOR, "off")

            # Close stale websocket before reconnecting
            if self.websocket:
                try:
                    await self.websocket.close()
                except Exception:
                    pass
                self.websocket = None

            if self.is_shutting_down:
                break

            PIHOME_LOGGER.info(f"Home Assistant: reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

    async def _send_message(self, message):
        await self.websocket.send(json.dumps(message))


    def add_listener(self, listener):
        self.listeners.append(listener)

    # ── HA React Listeners ─────────────────────────────────────────────────

    def add_react_listener(self, listener: HaReactListener):
        """Register a persistent react listener and persist to disk."""
        self.ha_react_listeners.append(listener)
        self._serialize_react_listeners()
        PIHOME_LOGGER.info(
            f"HaReactListener added: {listener.id} "
            f"({listener.entity_id} → {listener.state or 'any'})"
        )
        return listener.id

    def remove_react_listener(self, listener_id: str) -> bool:
        """Remove a react listener by ID and persist the change."""
        before = len(self.ha_react_listeners)
        self.ha_react_listeners = [
            l for l in self.ha_react_listeners if l.id != listener_id
        ]
        removed = len(self.ha_react_listeners) < before
        if removed:
            self._serialize_react_listeners()
            PIHOME_LOGGER.info(f"HaReactListener removed: {listener_id}")
        else:
            PIHOME_LOGGER.warn(f"HaReactListener not found for removal: {listener_id}")
        return removed

    def _serialize_react_listeners(self):
        data = [l.to_dict() for l in self.ha_react_listeners]
        try:
            with open(self.REACT_LISTENERS_FILE, "w") as f:
                json.dump(data, f, indent=2)
            PIHOME_LOGGER.info(
                f"Serialized {len(data)} HA react listener(s) to "
                f"{self.REACT_LISTENERS_FILE}"
            )
        except Exception as e:
            PIHOME_LOGGER.error(f"Failed to serialize HA react listeners: {e}")

    def _deserialize_react_listeners(self):
        if not os.path.exists(self.REACT_LISTENERS_FILE):
            return
        try:
            with open(self.REACT_LISTENERS_FILE, "r") as f:
                data = json.load(f)
            self.ha_react_listeners = [HaReactListener.from_dict(d) for d in data]
            PIHOME_LOGGER.info(
                f"Loaded {len(self.ha_react_listeners)} HA react listener(s) "
                f"from {self.REACT_LISTENERS_FILE}"
            )
        except Exception as e:
            PIHOME_LOGGER.error(f"Failed to deserialize HA react listeners: {e}")

    # ── Connection ─────────────────────────────────────────────────────────

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
            
            # Notify All Listeners
            for listener in self.listeners:
                listener.on_state_change(entity_id, state["state"], state)

            # Fire any matching HA-react listeners
            for react in list(self.ha_react_listeners):
                if react.matches(entity_id, state["state"]):
                    try:
                        PIHOME_LOGGER.info(
                            f"HaReactListener {react.id}: firing for "
                            f"{entity_id} → {state['state']}"
                        )
                        Clock.schedule_once(
                            lambda _dt, a=react.action:
                                PihomeEventFactory.create_event_from_dict(a).execute(),
                            0
                        )
                    except Exception as e:
                        PIHOME_LOGGER.error(
                            f"HaReactListener {react.id}: failed to fire action: {e}"
                        )

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
        print(f"Updating service: {service} with data: {data}")
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


class HomeAssistantListener:
    def __init__(self, callback):
        self.callback = callback

    def set_callback(self, callback):
        self.callback = callback

    def on_state_change(self, id, state, data):
        self.callback(id, state, data)


HOME_ASSISTANT = HomeAssistant()