from events.pihomeevent import PihomeEvent
from screens.BluetoothConnect.services.ble_service import BLE_SERVICE


class BluetoothSendEvent(PihomeEvent):
    """Send a line of text to a connected device.

    Lets PiHome drive an LED, buzzer or display on the hardware. The write is
    queued on the BLE loop, so this returns 202 rather than waiting for the
    radio to confirm delivery.
    """

    type = "bluetooth_send"

    def __init__(self, text=None, address=None, **kwargs):
        super().__init__()
        self.text = text
        self.address = address

    def execute(self):
        return BLE_SERVICE.send(self.text, address=self.address)

    def to_definition(self):
        return {
            "type": self.type,
            "text": self.type_def("string", True, "The line to send, e.g. led:on. A newline is added automatically"),
            "address": self.type_def("string", False, "Target device address. Optional when exactly one device is paired"),
        }
