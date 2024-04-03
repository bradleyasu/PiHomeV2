import json
import subprocess
from threading import Thread
from events.pihomeevent import PihomeEvent, PihomeEventFactory
from util.phlog import PIHOME_LOGGER


class ShellEvent(PihomeEvent):
    type = "shell"
    def __init__(self, command, args = "", on_complete = None, on_error = None, **kwargs):
        super().__init__()
        self.command = command
        self.args = args
        self.on_complete = on_complete
        self.on_error = on_error

    def execute(self):
        PIHOME_LOGGER.info(f"Executing shell command: {self.command} {self.args}")

        thread = Thread(target=self._execute, daemon=True)
        thread.start()
        return {
            "code": 200,
            "body": {"status": "success", "message": "Shell command executed and running in background"}
        }

    def _execute(self):
        # Execute the shell command
        process = subprocess.Popen([self.command, self.args], stdout=subprocess.PIPE)
        output, error = process.communicate()

        exit_code = process.returncode

        if exit_code == 0:
            if self.on_complete:
                self.replace_vars(self.on_complete, output)
                resp = PihomeEventFactory.create_event_from_dict(self.on_complete).execute()
                PIHOME_LOGGER.info("on_complete event executed: {}".format(resp))
            PIHOME_LOGGER.info(f"Shell command output: {output}")
        if exit_code != 0:
            if self.on_error:
                self.replace_vars(self.on_error, output)
                resp = PihomeEventFactory.create_event_from_dict(self.on_error).execute()
                PIHOME_LOGGER.info("on_error event executed: {}".format(resp))
            PIHOME_LOGGER.error(f"Shell command error: {output}")
        
    def replace_vars(self, event, data):
        """
        Event is a dict.  This function will iterate over all the values in the dict and replace any instance of $1 with the data value
        """
        # convert data from bytes to string
        data = data.decode("utf-8")
        for key in event:
            if isinstance(event[key], dict):
                self.replace_vars(event[key], data)
            elif isinstance(event[key], str):
                event[key] = event[key].replace("$1", data)

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "command": self.command,
            "args": self.args
        })

    def to_definition(self):
        return {
            "type": self.type,
            "command": self.type_def("string"),
            "args": self.type_def("string", False),
            "on_complete": self.type_def("event", False),
            "on_error": self.type_def("event", False),
        }