import base64
import json

from events.pihomeevent import PihomeEvent
from services.uploads.uploads import UPLOADS
from util.phlog import PIHOME_LOGGER


class UploadImageEvent(PihomeEvent):
    """Persist a user-uploaded image carried as base64 in the event payload.

    The web client posts ``{"type": "upload_image", "filename": "...",
    "data": "<base64>"}``.  ``data`` may include a ``data:image/...;base64,``
    URL prefix, which is stripped.  Not exposed in the event builder (no
    ``to_definition``) — it's driven programmatically by the client.
    """

    type = "upload_image"

    def __init__(self, filename=None, data=None, **kwargs):
        super().__init__()
        self.filename = filename
        self.data = data

    def execute(self):
        if not self.data:
            return {"code": 400, "body": {"status": "error", "message": "data is required"}}

        raw = self.data
        # Strip an optional data-URL prefix: "data:image/png;base64,XXXX"
        if isinstance(raw, str) and raw.startswith("data:") and "," in raw:
            raw = raw.split(",", 1)[1]

        try:
            decoded = base64.b64decode(raw, validate=False)
        except Exception as e:
            return {"code": 400, "body": {"status": "error", "message": "invalid base64: {}".format(e)}}

        try:
            name = UPLOADS.save_image(self.filename, decoded)
        except ValueError as e:
            return {"code": 400, "body": {"status": "error", "message": str(e)}}
        except Exception as e:
            PIHOME_LOGGER.error("UploadImageEvent: failed to save image: {}".format(e))
            return {"code": 500, "body": {"status": "error", "message": "failed to save image"}}

        return {
            "code": 200,
            "body": {"status": "success", "name": name, "url": "/uploads/{}".format(name)},
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "filename": self.filename,
            "data": self.data,
        })
