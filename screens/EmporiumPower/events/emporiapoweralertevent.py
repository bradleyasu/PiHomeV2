from events.pihomeevent import PihomeEvent
from screens.EmporiumPower.services.emporia_service import EMPORIA_SERVICE


class EmporiaPowerAlertEvent(PihomeEvent):
    """Create or update a power-threshold alert rule.

    When the named device's live draw crosses ``limit`` watts (rising or falling
    edge per ``direction``), the nested ``event`` is fired. Resending the same
    ``id`` updates the rule; rules persist across restarts.
    """

    type = "emporia_power_alert"

    def __init__(self, id=None, device=None, limit=None, direction="above",
                 cooldown=300, event=None, **kwargs):
        super().__init__()
        self.id = id
        self.device = device
        self.limit = limit
        self.direction = direction
        self.cooldown = cooldown
        self.event = event

    def execute(self):
        return EMPORIA_SERVICE.add_or_update_rule({
            "id": self.id,
            "device": self.device,
            "limit": self.limit,
            "direction": self.direction,
            "cooldown": self.cooldown,
            "event": self.event,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "id": self.type_def("string", True, "Unique id for this rule (resend the same id to update it)"),
            "device": self.type_def("string", True, "Circuit name as shown on the Power screen, or 'Whole Home'"),
            "limit": self.type_def("number", True, "Threshold in watts"),
            "direction": self.type_def("option", False, "Fire when crossing above or below the limit",
                                       {"above": "above", "below": "below"}),
            "cooldown": self.type_def("integer", False, "Minimum seconds between fires (default 300)"),
            "event": self.type_def("event", True, "The PiHome event to fire when the threshold is crossed"),
        }
