import json

from events.pihomeevent import PihomeEvent
from services.uploads.uploads import UPLOADS


class ListUploadsEvent(PihomeEvent):
    """Return the list of user-uploaded images for the web gallery."""

    type = "list_uploads"

    def __init__(self, album="Default", offset=0, limit=24, **kwargs):
        super().__init__()
        self.album = album or "Default"
        self.offset = offset
        self.limit = limit

    def execute(self):
        page = UPLOADS.list_page(self.album, self.offset, self.limit)
        uploads = [
            {"name": name, "url": "/uploads/{}/{}".format(self.album, name)}
            for name in page["names"]
        ]
        return {
            "code": 200,
            "body": {
                "status": "success",
                "album": self.album,
                "uploads": uploads,
                "total": page["total"],
                "offset": page["offset"],
                "limit": page["limit"],
            },
        }

    def to_json(self):
        return json.dumps({
            "type": self.type, "album": self.album,
            "offset": self.offset, "limit": self.limit,
        })
