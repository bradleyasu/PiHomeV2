import json

from events.pihomeevent import PihomeEvent
from services.uploads.uploads import UPLOADS, DEFAULT_ALBUM
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER


class DeleteAlbumEvent(PihomeEvent):
    """Delete an album and all images inside it.

    Refuses to delete the Default album. If the deleted album was the active
    wallpaper album, reset the active album to Default and restart the wallpaper
    rotation so it doesn't point at a removed directory.
    """

    type = "delete_album"

    def __init__(self, name=None, **kwargs):
        super().__init__()
        self.name = name

    def execute(self):
        if not self.name:
            return {"code": 400, "body": {"status": "error", "message": "name is required"}}

        deleted = UPLOADS.delete_album(self.name)
        if not deleted:
            return {"code": 400, "body": {"status": "error",
                                          "message": "could not delete album (missing or protected)"}}

        try:
            active = CONFIG.get("wallpaper", "uploads_album", DEFAULT_ALBUM)
            if active == self.name:
                CONFIG.set("wallpaper", "uploads_album", DEFAULT_ALBUM)
                from services.wallpaper.wallpaper import WALLPAPER_SERVICE
                if WALLPAPER_SERVICE.repo == "My Uploads":
                    WALLPAPER_SERVICE.restart()
        except Exception as e:
            PIHOME_LOGGER.error("DeleteAlbumEvent: active-album reassignment failed: {}".format(e))

        return {"code": 200, "body": {"status": "success", "name": self.name}}

    def to_json(self):
        return json.dumps({"type": self.type, "name": self.name})
