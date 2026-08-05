from events.pihomeevent import PihomeEvent
from screens.BluetoothConnect.services.ble_service import BLE_SERVICE


class BluetoothUnbindEvent(PihomeEvent):
    """Remove the binding for a command token."""

    type = "bluetooth_unbind"

    def __init__(self, command=None, device=None, **kwargs):
        super().__init__()
        self.command = command
        self.device = device

    def execute(self):
        return BLE_SERVICE.unbind(self.command, device=self.device)

    def to_definition(self):
        return {
            "type": self.type,
            "command": self.type_def("string", True, "The command token to unbind"),
            "device": self.type_def("string", False, "Device address, if the binding was restricted to one device"),
        }
