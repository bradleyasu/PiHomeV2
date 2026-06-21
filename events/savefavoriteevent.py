import json
import os

from events.pihomeevent import PihomeEvent
from util.phlog import PIHOME_LOGGER

FAVORITES_FILE = "./cache/favorite_events.json"


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def _normalize(favorites):
    """Normalize favorites to the wrapped shape ``{name: {event, show_on_home}}``.

    Legacy entries were stored flat (``{name: event}``); migrate any such bare
    event into the wrapped form with ``show_on_home`` defaulting to False so
    existing favorites stay off the home screen until opted in.  Returns
    ``(normalized_dict, changed_bool)``.
    """
    normalized = {}
    changed = False
    for name, entry in favorites.items():
        if isinstance(entry, dict) and isinstance(entry.get("event"), dict):
            normalized[name] = {
                "event": entry["event"],
                "show_on_home": _coerce_bool(entry.get("show_on_home", False)),
            }
        else:
            # Legacy flat event (or anything unexpected) -> wrap it.
            normalized[name] = {"event": entry, "show_on_home": False}
            changed = True
    return normalized, changed


def _load_favorites():
    """Load favorites, normalized to the wrapped shape (migrating legacy data)."""
    if not os.path.isfile(FAVORITES_FILE):
        return {}
    try:
        with open(FAVORITES_FILE, "r") as f:
            raw = json.load(f)
    except Exception as e:
        PIHOME_LOGGER.error("Failed to load favorite events: {}".format(e))
        return {}

    normalized, changed = _normalize(raw)
    if changed:
        PIHOME_LOGGER.info("Favorites: migrated legacy entries to wrapped format")
        _save_favorites(normalized)
    return normalized


def _save_favorites(favorites):
    os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favorites, f, indent=2)


class SaveFavoriteEvent(PihomeEvent):
    type = "save_favorite"

    def __init__(self, name, event, show_on_home=False, **kwargs):
        super().__init__()
        self.name = name
        self.event = event
        self.show_on_home = show_on_home

    def execute(self):
        if not self.name or not self.event:
            return {
                "code": 400,
                "body": {"status": "error", "message": "name and event are required"}
            }

        favorites = _load_favorites()
        favorites[self.name] = {
            "event": self.event,
            "show_on_home": _coerce_bool(self.show_on_home),
        }
        _save_favorites(favorites)

        PIHOME_LOGGER.info("Saved favorite event: {}".format(self.name))
        return {
            "code": 200,
            "body": {"status": "success", "message": "Favorite '{}' saved".format(self.name)}
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "name": self.name,
            "event": self.event,
            "show_on_home": self.show_on_home,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "name": self.type_def("string", True, "Name for the favorite (spaces allowed)"),
            "event": self.type_def("event", True, "PiHome event to persist as a favorite"),
            "show_on_home": self.type_def("bool", False, "Show this event on the home screen"),
        }
