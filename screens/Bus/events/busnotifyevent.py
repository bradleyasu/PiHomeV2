import json
import math
from datetime import datetime as dt

from events.pihomeevent import PihomeEvent, PihomeEventFactory
from networking.poller import POLLER
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER


class BusNotifyEvent(PihomeEvent):
    """Monitor a bus route and fire an event when ETA reaches a threshold."""

    type = "bus_notify"

    PRT_API = "https://realtime.portauthority.org/bustime/api/v3/getpredictions?rtpidatafeed=Port Authority Bus&key={}&format=json&rt={}&stpid={}"

    def __init__(self, route, minutes, on_trigger, **kwargs):
        super().__init__()
        self.route = str(route) if route is not None else None
        self.minutes = int(minutes) if minutes is not None else None
        self.on_trigger = on_trigger
        self._poller_key = None

    def execute(self):
        if not self.route or self.minutes is None or not self.on_trigger:
            return {
                "code": 400,
                "body": {"status": "error", "message": "route, minutes, and on_trigger are required"}
            }

        api_key = CONFIG.get("prt", "api_key", "").strip()
        stops = CONFIG.get("prt", "stops", "").strip()

        if not api_key or not stops:
            return {
                "code": 400,
                "body": {"status": "error", "message": "PRT api_key and stops must be configured in settings"}
            }

        url = self.PRT_API.format(api_key, self.route, stops)
        self._poller_key = POLLER.register_api(url, 60, lambda data: self._on_poll(data))

        PIHOME_LOGGER.info(
            "BusNotify: watching route {} for ETA <= {} min".format(self.route, self.minutes)
        )
        return {
            "code": 200,
            "body": {
                "status": "success",
                "message": "Monitoring route {} — will trigger when ETA <= {} min".format(
                    self.route, self.minutes
                ),
                "poller_key": self._poller_key,
            }
        }

    def _on_poll(self, payload):
        try:
            response = payload.get("bustime-response", {})
            predictions = response.get("prd", [])
            now = dt.now()

            for pred in predictions:
                if pred.get("rt") != self.route:
                    continue
                prdtm = pred.get("prdtm")
                if not prdtm:
                    continue

                eta_time = dt.strptime(prdtm, "%Y%m%d %H:%M")
                eta_minutes = math.floor((eta_time - now).total_seconds() / 60.0)

                if eta_minutes <= self.minutes:
                    PIHOME_LOGGER.info(
                        "BusNotify: route {} ETA {} min (<= {} min) — firing event".format(
                            self.route, eta_minutes, self.minutes
                        )
                    )
                    self._cleanup()
                    PihomeEventFactory.create_event_from_dict(self.on_trigger).execute()
                    return

        except Exception as e:
            PIHOME_LOGGER.error("BusNotify: poll error: {}".format(e))

    def _cleanup(self):
        if self._poller_key is not None:
            POLLER.unregister_api(self._poller_key)
            self._poller_key = None

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "route": self.route,
            "minutes": self.minutes,
            "on_trigger": self.on_trigger,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "route": self.type_def("string", True, "Bus route number to monitor (e.g. '51')"),
            "minutes": self.type_def("integer", True, "ETA threshold in minutes — triggers when a bus is this close or closer"),
            "on_trigger": self.type_def("event", True, "PiHome event to execute when the ETA threshold is reached"),
        }
