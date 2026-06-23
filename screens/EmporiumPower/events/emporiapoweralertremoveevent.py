from events.pihomeevent import PihomeEvent
from screens.EmporiumPower.services.emporia_service import EMPORIA_SERVICE


class EmporiaPowerAlertRemoveEvent(PihomeEvent):
    """Remove a previously-created power-threshold alert rule by id."""

    type = "emporia_power_alert_remove"

    def __init__(self, id=None, **kwargs):
        super().__init__()
        self.id = id

    def execute(self):
        return EMPORIA_SERVICE.remove_rule(self.id)

    def to_definition(self):
        return {
            "type": self.type,
            "id": self.type_def("string", True, "Id of the alert rule to remove"),
        }
