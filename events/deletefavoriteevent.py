import json

from events.pihomeevent import PihomeEvent
from events.savefavoriteevent import _load_favorites, _save_favorites
from util.phlog import PIHOME_LOGGER


class DeleteFavoriteEvent(PihomeEvent):
    type = "delete_favorite"

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

        del favorites[self.name]
        _save_favorites(favorites)

        PIHOME_LOGGER.info("Deleted favorite event: {}".format(self.name))
        return {
            "code": 200,
            "body": {"status": "success", "message": "Favorite '{}' deleted".format(self.name)}
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "name": self.name,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "name": self.type_def("string", True, "Name of the favorite to delete"),
        }
