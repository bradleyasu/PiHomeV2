from events.pihomeevent import PihomeEvent
from screens.EmporiumPower.services.emporia_service import EMPORIA_SERVICE


class EmporiaPowerAlertsListEvent(PihomeEvent):
    """Return all currently-configured power-threshold alert rules."""

    type = "emporia_power_alerts_list"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        return EMPORIA_SERVICE.list_rules()

    def to_definition(self):
        return {"type": self.type}
