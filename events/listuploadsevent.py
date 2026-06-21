import json

from events.pihomeevent import PihomeEvent
from services.uploads.uploads import UPLOADS


class ListUploadsEvent(PihomeEvent):
    """Return the list of user-uploaded images for the web gallery."""

    type = "list_uploads"

    def __init__(self, offset=0, limit=24, **kwargs):
        super().__init__()
        self.offset = offset
        self.limit = limit

    def execute(self):
        page = UPLOADS.list_page(self.offset, self.limit)
        uploads = [
            {"name": name, "url": "/uploads/{}".format(name)}
            for name in page["names"]
        ]
        return {
            "code": 200,
            "body": {
                "status": "success",
                "uploads": uploads,
                "total": page["total"],
                "offset": page["offset"],
                "limit": page["limit"],
            },
        }

    def to_json(self):
        return json.dumps({"type": self.type, "offset": self.offset, "limit": self.limit})
