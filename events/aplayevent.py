import json
import re
import subprocess
from threading import Thread

from events.pihomeevent import PihomeEvent
from util.phlog import PIHOME_LOGGER


def _discover_devices():
    """Parse `aplay -l` output into a list of ALSA device strings (e.g. 'hw:0,0')."""
    devices = []
    try:
        output = subprocess.check_output(["aplay", "-l"], stderr=subprocess.DEVNULL, timeout=5).decode("utf-8")
        for match in re.finditer(r"card (\d+):.*device (\d+):", output):
            card, device = match.group(1), match.group(2)
            devices.append("hw:{},{}".format(card, device))
    except Exception as e:
        PIHOME_LOGGER.error("aplay: failed to discover devices: {}".format(e))
    return devices


class AplayEvent(PihomeEvent):
    type = "aplay"

    def __init__(self, path, device=None, **kwargs):
        super().__init__()
        self.path = path
        self.device = device

    def execute(self):
        if not self.path:
            return {
                "code": 400,
                "body": {"status": "error", "message": "path is required"}
            }

        cmd = ["aplay"]
        if self.device:
            cmd += ["-D", self.device]
        cmd.append(self.path)

        PIHOME_LOGGER.info("aplay: playing {} on {}".format(self.path, self.device or "default"))
        thread = Thread(target=self._run, args=(cmd,), daemon=True)
        thread.start()

        return {
            "code": 200,
            "body": {"status": "success", "message": "Playing {} on {}".format(self.path, self.device or "default")}
        }

    def _run(self, cmd):
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        except subprocess.TimeoutExpired:
            PIHOME_LOGGER.warning("aplay: playback timed out for {}".format(self.path))
        except Exception as e:
            PIHOME_LOGGER.error("aplay: playback error: {}".format(e))

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "path": self.path,
            "device": self.device,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "path": self.type_def("string", True, "Path to the audio file to play"),
            "device": self.type_def("option", False, "ALSA output device", _discover_devices()),
        }
