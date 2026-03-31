import json
import os

from events.pihomeevent import PihomeEvent
from util.phlog import PIHOME_LOGGER

FAVORITES_FILE = "./cache/favorite_events.json"


def _load_favorites():
    if not os.path.isfile(FAVORITES_FILE):
        return {}
    try:
        with open(FAVORITES_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        PIHOME_LOGGER.error("Failed to load favorite events: {}".format(e))
        return {}


def _save_favorites(favorites):
    os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favorites, f, indent=2)


class SaveFavoriteEvent(PihomeEvent):
    type = "save_favorite"

    def __init__(self, name, event, **kwargs):
        super().__init__()
        self.name = name
        self.event = event

    def execute(self):
        if not self.name or not self.event:
            return {
                "code": 400,
                "body": {"status": "error", "message": "name and event are required"}
            }

        favorites = _load_favorites()
        favorites[self.name] = self.event
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
        })

    def to_definition(self):
        return {
            "type": self.type,
            "name": self.type_def("string", True, "Name for the favorite (spaces allowed)"),
            "event": self.type_def("event", True, "PiHome event to persist as a favorite"),
        }
