from events.pihomeevent import PihomeEvent
from screens.BambuLab.bambustate import TRIGGER_LABELS, TRIGGERS
from screens.BambuLab.services.bambu_service import BAMBU_SERVICE


class BambuLabStateAlertEvent(PihomeEvent):
    """Fire a PiHome event whenever the printer enters a given state.

    Bind a printer state — PRINTING, COMPLETE, FAILED, an error, or the printer
    going on/offline — to any nested PiHome event. The binding is edge-triggered
    (it fires on entering the state, never repeatedly) and is evaluated by the
    always-on BambuLab service, so it works whichever screen is open.

    ``id`` is optional: omit it and one is generated, resend the same id to update
    an existing binding. Bindings persist across restarts.

    The nested event may interpolate live values with ``$name`` placeholders:
    ``$state`` ``$state_label`` ``$job`` ``$progress`` ``$layer`` ``$layer_total``
    ``$eta`` ``$eta_text`` ``$finish`` ``$error`` ``$nozzle`` ``$bed``.

    Webhook / task payload example::

        {"type": "bambulab_state_alert",
         "state": "FINISH",
         "event": {"type": "notification",
                   "title": "Print complete",
                   "description": "$job finished at $progress%"}}
    """

    type = "bambulab_state_alert"

    def __init__(self, id=None, state=None, event=None, cooldown=0, **kwargs):
        super().__init__()
        self.id = id
        self.state = state
        self.event = event
        self.cooldown = cooldown

    def execute(self):
        return BAMBU_SERVICE.add_or_update_rule({
            "id": self.id,
            "state": self.state,
            "event": self.event,
            "cooldown": self.cooldown,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "id": self.type_def("string", False,
                                "Optional id — resend the same id to update this binding"),
            "state": self.type_def("option", True, "Printer state that triggers the event",
                                   {s: TRIGGER_LABELS.get(s, s) for s in TRIGGERS}),
            "event": self.type_def("event", True,
                                   "The PiHome event to fire when the printer enters this state"),
            "cooldown": self.type_def("integer", False,
                                      "Minimum seconds between fires (default 0 = no limit)"),
        }
