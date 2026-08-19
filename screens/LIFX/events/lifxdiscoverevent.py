"""``lifx_discover`` - force a discovery sweep now.

The service re-scans on its own schedule; this is for after plugging in a new
bulb, or renaming one in the LIFX app.
"""

from events.pihomeevent import PihomeEvent

try:
    from screens.LIFX.services.lifx_service import LIFX_SERVICE
except ImportError:
    LIFX_SERVICE = None


class LifxDiscoverEvent(PihomeEvent):
    type = "lifx_discover"

    def __init__(self, wait=None, **kwargs):
        super().__init__()
        self.wait = wait

    def execute(self):
        if LIFX_SERVICE is None:
            return {"code": 503, "body": {
                "status": "error", "error_code": "no_devices",
                "message": "The LIFX screen is not installed"}}

        # Default is fire-and-forget: a sweep takes several seconds and
        # execute() runs on the Kivy main thread.
        blocking = str(self.wait).strip().lower() in ("1", "true", "yes")
        return LIFX_SERVICE.discover_now(blocking=blocking)

    def to_definition(self):
        return {
            "type": self.type,
            "wait": self.type_def(
                "string", False,
                "Set to 1 to block until the sweep finishes and return the count. "
                "Takes several seconds."),
        }
