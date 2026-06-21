import json

from events.pihomeevent import PihomeEvent
from services.uploads.uploads import UPLOADS
from util.configuration import CONFIG


class ListAlbumsEvent(PihomeEvent):
    """Return all upload albums (with image counts) and the active album."""

    type = "list_albums"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        active = CONFIG.get("wallpaper", "uploads_album", "Default")
        return {
            "code": 200,
            "body": {"status": "success", "albums": UPLOADS.list_albums(), "active": active},
        }

    def to_json(self):
        return json.dumps({"type": self.type})
