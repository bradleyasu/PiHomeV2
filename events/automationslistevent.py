from events.pihomeevent import PihomeEvent
from util.rulestore import RULE_STORES


class AutomationsListEvent(PihomeEvent):
    """List every automation rule from every registered store.

    PiHome's trigger -> event rules live in per-service stores (BambuLab printer
    states, Emporia power thresholds, Bluetooth command bindings, AirPlay and
    Home Assistant react listeners). This aggregates them all into one response,
    which is what the Automations screen shows and the easiest way to audit every
    rule at once without calling each service's own list event.

    Each entry carries a human-readable ``trigger`` and ``action`` alongside the
    raw rule, so a client can render it without knowing the store's schema.

    Webhook / task payload example::

        {"type": "automations_list"}

    Optionally narrow it to one store::

        {"type": "automations_list", "store": "bambulab"}
    """

    type = "automations_list"

    def __init__(self, store=None, **kwargs):
        super().__init__()
        self.store = store

    def execute(self):
        wanted = str(self.store or "").strip()
        if wanted and wanted not in RULE_STORES:
            return {"code": 404, "body": {
                "status": "error",
                "message": f"No automation store '{wanted}'",
                "stores": sorted(RULE_STORES)}}

        stores = []
        total = 0
        for key, store in RULE_STORES.items():
            if wanted and key != wanted:
                continue
            rules = store.list()["body"].get("rules", [])
            total += len(rules)
            stores.append({
                "key": key,
                "label": store.label,
                # The event type that creates a rule here — so a client can
                # discover how to add one without reading the source.
                "create_event": getattr(store, "create_event", None),
                "supports_enable": getattr(store, "supports_enable", True),
                "rules": [{
                    "id": rule.get("id"),
                    "trigger": store.describe(rule),
                    "action": store.describe_action(rule),
                    "enabled": rule.get("enabled", True),
                    "last_fired": rule.get("last_fired"),
                    "rule": rule,
                } for rule in rules],
            })

        return {"code": 200, "body": {
            "status": "success",
            "message": f"{total} automation(s) across {len(stores)} store(s)",
            "count": total,
            "stores": stores}}

    def to_definition(self):
        return {
            "type": self.type,
            "store": self.type_def("option", False,
                                   "Limit to one store (omit for all)",
                                   {k: getattr(s, "label", k)
                                    for k, s in RULE_STORES.items()}),
        }
