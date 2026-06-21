import json

from events.pihomeevent import PihomeEvent
from services.uploads.uploads import UPLOADS


class CreateAlbumEvent(PihomeEvent):
    """Create a new (empty) upload album."""

    type = "create_album"

    def __init__(self, name=None, **kwargs):
        super().__init__()
        self.name = name

    def execute(self):
        created = UPLOADS.create_album(self.name)
        if created is None:
            return {"code": 400, "body": {"status": "error", "message": "invalid album name"}}
        return {"code": 200, "body": {"status": "success", "name": created}}

    def to_json(self):
        return json.dumps({"type": self.type, "name": self.name})
