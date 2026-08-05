from events.pihomeevent import PihomeEvent
from screens.BluetoothConnect.services.ble_service import BLE_SERVICE


class BluetoothDevicesListEvent(PihomeEvent):
    """Return the paired devices with their live connection state."""

    type = "bluetooth_devices_list"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        return BLE_SERVICE.list_devices()

    def to_definition(self):
        return {"type": self.type}
