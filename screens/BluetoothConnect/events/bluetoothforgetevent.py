from events.pihomeevent import PihomeEvent
from screens.BluetoothConnect.services.ble_service import BLE_SERVICE


class BluetoothForgetEvent(PihomeEvent):
    """Un-pair a device. PiHome disconnects it and stops accepting its commands."""

    type = "bluetooth_forget"

    def __init__(self, address=None, **kwargs):
        super().__init__()
        self.address = address

    def execute(self):
        return BLE_SERVICE.forget(self.address)

    def to_definition(self):
        return {
            "type": self.type,
            "address": self.type_def("string", True, "Address of the paired device to forget"),
        }
