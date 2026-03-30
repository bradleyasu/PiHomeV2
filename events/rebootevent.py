import json
import subprocess
from threading import Thread

from events.pihomeevent import PihomeEvent
from util.phlog import PIHOME_LOGGER


class RebootEvent(PihomeEvent):
    type = "reboot"
    def __init__(self, action="reboot", **kwargs):
        super().__init__()
        self.action = action

    def execute(self):
        if self.action == "reboot":
            PIHOME_LOGGER.info("RebootEvent: rebooting system")
            Thread(target=lambda: subprocess.Popen(["sudo", "reboot"]), daemon=True).start()
            return {
                "code": 200,
                "body": {"status": "success", "message": "System rebooting"}
            }
        elif self.action == "shutdown":
            PIHOME_LOGGER.info("RebootEvent: shutting down system")
            Thread(target=lambda: subprocess.Popen(["sudo", "shutdown", "-h", "now"]), daemon=True).start()
            return {
                "code": 200,
                "body": {"status": "success", "message": "System shutting down"}
            }
        elif self.action == "restart_pihome":
            PIHOME_LOGGER.info("RebootEvent: restarting PiHome app")
            from util.helpers import get_app
            get_app().quit()
            return {
                "code": 200,
                "body": {"status": "success", "message": "PiHome app restarting"}
            }
        else:
            return {
                "code": 400,
                "body": {"status": "error", "message": "Invalid action: {}".format(self.action)}
            }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "action": self.action
        })

    def to_definition(self):
        return {
            "type": self.type,
            "action": self.type_def("option", required=False, description="System action to perform", options=["reboot", "shutdown", "restart_pihome"]),
        }
