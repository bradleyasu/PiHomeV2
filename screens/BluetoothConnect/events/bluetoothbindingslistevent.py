from events.pihomeevent import PihomeEvent
from screens.BluetoothConnect.services.ble_service import BLE_SERVICE


class BluetoothBindingsListEvent(PihomeEvent):
    """Return every configured command binding."""

    type = "bluetooth_bindings_list"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        return BLE_SERVICE.list_bindings()

    def to_definition(self):
        return {"type": self.type}
