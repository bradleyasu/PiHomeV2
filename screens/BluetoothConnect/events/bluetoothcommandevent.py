from events.pihomeevent import PihomeEvent
from screens.BluetoothConnect.services.ble_service import BLE_SERVICE


class BluetoothCommandEvent(PihomeEvent):
    """Fire whatever is bound to a command token.

    This is the same path a real BLE device takes when it sends that token, so
    it is the way to test a binding before any hardware exists -- or to reuse a
    binding from MQTT, HTTP or the web UI.
    """

    type = "bluetooth_command"

    def __init__(self, command=None, value=None, device=None, **kwargs):
        super().__init__()
        self.command = command
        self.value = value
        self.device = device

    def execute(self):
        return BLE_SERVICE.dispatch_command(self.command, self.value, address=self.device)

    def to_definition(self):
        return {
            "type": self.type,
            "command": self.type_def("string", True, "The command token to fire, e.g. button_a"),
            "value": self.type_def("string", False, "Optional value, substituted for $1 in the bound event"),
            "device": self.type_def("string", False, "Address of the device to attribute this to. Selects a device-specific binding over the wildcard"),
        }
