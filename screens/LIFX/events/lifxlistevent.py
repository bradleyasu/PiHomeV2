"""``lifx_list`` - what bulbs and rooms exist.

This is how anything driving the API discovers which strings are legal as a
``lifx`` target, so it is worth keeping accurate.  Reads the cached registry;
no network traffic.
"""

from events.pihomeevent import PihomeEvent
from screens.LIFX import protocol as p

try:
    from screens.LIFX.services.lifx_service import LIFX_SERVICE
except ImportError:
    LIFX_SERVICE = None


class LifxListEvent(PihomeEvent):
    type = "lifx_list"

    def __init__(self, room=None, **kwargs):
        super().__init__()
        self.room = room

    def execute(self):
        if LIFX_SERVICE is None:
            return {"code": 503, "body": {
                "status": "error", "error_code": "no_devices",
                "message": "The LIFX screen is not installed"}}

        snapshot = LIFX_SERVICE.get_snapshot()
        registry = snapshot["bulbs"]
        rooms = snapshot["rooms"]

        wanted = (self.room or "").strip().lower()
        if wanted:
            rooms = [r for r in rooms if r["name"].lower() == wanted]
            allowed = {s for r in rooms for s in r["serials"]}
            registry = {s: e for s, e in registry.items() if s in allowed}

        bulbs = []
        for serial in sorted(registry, key=lambda s: (registry[s].get("label") or "")):
            entry = registry[serial]
            hue, saturation, brightness, kelvin = p.hsbk_to_pct(
                entry.get("hue", 0) or 0, entry.get("saturation", 0) or 0,
                entry.get("brightness", 0) or 0, entry.get("kelvin", 3500) or 3500)
            bulbs.append({
                "serial": serial,
                "label": entry.get("label") or serial,
                "room": entry.get("group") or "Ungrouped",
                "ip": entry.get("ip") or "",
                "power": "on" if entry.get("power") else "off",
                "brightness": round(brightness, 1),
                "hue": round(hue, 1),
                "saturation": round(saturation, 1),
                "kelvin": kelvin,
                "color": bool(entry.get("color", True)),
                "kelvin_range": entry.get("kelvin_range") or [p.KELVIN_MIN,
                                                              p.KELVIN_MAX],
                "product": p.product_info(entry.get("product", 0))["name"],
                "online": bool(entry.get("online", True)),
            })

        return {"code": 200, "body": {
            "status": "success",
            "message": "{} bulb(s) in {} room(s)".format(len(bulbs), len(rooms)),
            "count": len(bulbs),
            "rooms": [{"name": r["name"], "serials": r["serials"],
                       "count": r["count"], "any_on": r["any_on"]} for r in rooms],
            "bulbs": bulbs,
            "last_discovery": snapshot["last_discovery"],
            "enabled": snapshot["enabled"],
        }}

    def to_definition(self):
        return {
            "type": self.type,
            "room": self.type_def("string", False,
                                  "Limit the listing to one room"),
        }
