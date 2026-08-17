from events.pihomeevent import PihomeEvent
from screens.BambuLab.services.bambu_service import BAMBU_SERVICE


class BambuLabStateAlertRemoveEvent(PihomeEvent):
    """Delete a registered BambuLab state alert by id.

    Use ``bambulab_state_alerts_list`` to find the id.

    Webhook / task payload example::

        {"type": "bambulab_state_alert_remove", "id": "print-done"}
    """

    type = "bambulab_state_alert_remove"

    def __init__(self, id=None, **kwargs):
        super().__init__()
        self.id = id

    def execute(self):
        if not self.id:
            return {"code": 400,
                    "body": {"status": "error", "message": "'id' is required"}}
        return BAMBU_SERVICE.remove_rule(self.id)

    def to_definition(self):
        # Options are built from the live rule store so the event builder offers a
        # dropdown of what is actually registered (same trick as FavoriteEvent).
        rules = BAMBU_SERVICE.list_rules()["body"].get("rules", [])
        options = {r["id"]: f"{r['id']}  ({r.get('state')})" for r in rules}
        return {
            "type": self.type,
            "id": self.type_def("option", True, "Id of the state alert to delete", options),
        }
