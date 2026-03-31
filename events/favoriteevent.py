import json

from events.pihomeevent import PihomeEvent, PihomeEventFactory
from events.savefavoriteevent import _load_favorites
from util.phlog import PIHOME_LOGGER


class FavoriteEvent(PihomeEvent):
    type = "favorite"

    def __init__(self, name, **kwargs):
        super().__init__()
        self.name = name

    def execute(self):
        if not self.name:
            return {
                "code": 400,
                "body": {"status": "error", "message": "name is required"}
            }

        favorites = _load_favorites()
        if self.name not in favorites:
            return {
                "code": 404,
                "body": {"status": "error", "message": "Favorite '{}' not found".format(self.name)}
            }

        PIHOME_LOGGER.info("Executing favorite event: {}".format(self.name))
        return PihomeEventFactory.create_event_from_dict(favorites[self.name]).execute()

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "name": self.name,
        })

    def to_definition(self):
        favorites = _load_favorites()
        return {
            "type": self.type,
            "name": self.type_def("option", True, "Name of the favorite to execute", list(favorites.keys())),
        }
