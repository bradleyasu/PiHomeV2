from events.pihomeevent import PihomeEvent
from screens.BambuLab.services.bambu_service import BAMBU_SERVICE


class BambuLabStateAlertsListEvent(PihomeEvent):
    """List every registered BambuLab state alert.

    Returns each binding's id, the state it watches, its cooldown, and the event
    it fires — the ids are what ``bambulab_state_alert_remove`` deletes.

    Webhook / task payload example::

        {"type": "bambulab_state_alerts_list"}
    """

    type = "bambulab_state_alerts_list"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        return BAMBU_SERVICE.list_rules()

    def to_definition(self):
        return {"type": self.type}
