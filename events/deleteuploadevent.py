import json
import os

from events.pihomeevent import PihomeEvent
from services.uploads.uploads import UPLOADS
from util.phlog import PIHOME_LOGGER


class DeleteUploadEvent(PihomeEvent):
    """Delete a user-uploaded image by name.

    If the deleted image is the wallpaper currently on screen, reshuffle so the
    display doesn't point at a missing file.
    """

    type = "delete_upload"

    def __init__(self, name=None, **kwargs):
        super().__init__()
        self.name = name

    def execute(self):
        if not self.name:
            return {"code": 400, "body": {"status": "error", "message": "name is required"}}

        # Capture the resolved path before deletion so we can tell whether the
        # current wallpaper pointed at this image.
        from services.wallpaper.wallpaper import WALLPAPER_SERVICE
        target_path = UPLOADS.path_for(self.name)

        deleted = UPLOADS.delete_image(self.name)
        if not deleted:
            return {"code": 404, "body": {"status": "error", "message": "not found"}}

        try:
            in_use = (
                WALLPAPER_SERVICE.repo == "My Uploads"
                and target_path is not None
                and os.path.basename(WALLPAPER_SERVICE.source or "") == os.path.basename(target_path)
            )
            if in_use:
                WALLPAPER_SERVICE.shuffle()
        except Exception as e:
            PIHOME_LOGGER.error("DeleteUploadEvent: reshuffle check failed: {}".format(e))

        return {"code": 200, "body": {"status": "success", "name": self.name}}

    def to_json(self):
        return json.dumps({"type": self.type, "name": self.name})
