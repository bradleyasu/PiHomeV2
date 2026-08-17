from events.pihomeevent import PihomeEvent
from screens.BambuLab.bambustate import TRIGGER_LABELS, TRIGGERS, normalize_trigger
from screens.BambuLab.services.bambu_service import BAMBU_SERVICE


class BambuLabStateTestEvent(PihomeEvent):
    """Fire every state alert bound to a given state, right now.

    This is the same path a real printer transition takes (placeholders are
    substituted from the current snapshot), so it is the way to verify a binding
    without waiting for an actual print to reach that state.

    Webhook / task payload example::

        {"type": "bambulab_state_test", "state": "FINISH"}
    """

    type = "bambulab_state_test"

    def __init__(self, state=None, **kwargs):
        super().__init__()
        self.state = state

    def execute(self):
        trigger = normalize_trigger(self.state)
        if trigger is None:
            return {"code": 400, "body": {
                "status": "error",
                "message": f"'state' must be one of: {', '.join(TRIGGERS)}"}}

        count = BAMBU_SERVICE.fire_trigger(trigger)
        if count == 0:
            return {"code": 404, "body": {
                "status": "error",
                "message": f"No state alerts registered for {trigger}"}}
        return {"code": 200, "body": {
            "status": "success",
            "message": f"Fired {count} state alert(s) for {trigger}",
            "state": trigger, "count": count}}

    def to_definition(self):
        return {
            "type": self.type,
            "state": self.type_def("option", True, "Printer state to simulate",
                                   {s: TRIGGER_LABELS.get(s, s) for s in TRIGGERS}),
        }
