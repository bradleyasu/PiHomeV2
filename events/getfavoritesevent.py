import json

from events.pihomeevent import PihomeEvent
from events.savefavoriteevent import _load_favorites


class GetFavoritesEvent(PihomeEvent):
    type = "get_favorites"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        favorites = _load_favorites()
        return {
            "code": 200,
            "body": {"status": "success", "count": len(favorites), "favorites": favorites}
        }

    def to_json(self):
        return json.dumps({"type": self.type})

    def to_definition(self):
        return {
            "type": self.type,
        }
