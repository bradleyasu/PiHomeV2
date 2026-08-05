from events.pihomeevent import PihomeEvent
from screens.BluetoothConnect.services.ble_service import BLE_SERVICE


class BluetoothBindEvent(PihomeEvent):
    """Bind a command token from a BLE device to a PiHome event.

    When the device sends that token, the nested event fires. Re-sending the
    same command (and device) replaces the binding. Bindings persist across
    restarts in cache/bluetooth_bindings.json.

    Any "$1" in the nested event is replaced with the value the device sent, so
    binding "dial" to {"type": "brightness", "level": "$1"} lets a physical knob
    send "dial:80".
    """

    type = "bluetooth_bind"

    def __init__(self, command=None, event=None, device=None, description=None, **kwargs):
        super().__init__()
        self.command = command
        self.event = event
        self.device = device
        self.description = description

    def execute(self):
        return BLE_SERVICE.bind(self.command, self.event,
                                device=self.device, description=self.description)

    def to_definition(self):
        return {
            "type": self.type,
            "command": self.type_def("string", True, "The token the device sends, e.g. button_a"),
            "event": self.type_def("event", True, "The PiHome event to fire when the token arrives"),
            "device": self.type_def("string", False, "Restrict this binding to one device address. Omit to accept the token from any paired device"),
            "description": self.type_def("string", False, "Optional note shown on the Bluetooth screen"),
        }
