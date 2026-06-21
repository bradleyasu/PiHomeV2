import json

from events.pihomeevent import PihomeEvent
from services.uploads.uploads import UPLOADS
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER


class RenameAlbumEvent(PihomeEvent):
    """Rename an album. Refuses to rename the Default album.

    If the renamed album was the active wallpaper album, update the active-album
    pointer to the new name (and restart rotation if it's the live source).
    """

    type = "rename_album"

    def __init__(self, name=None, new_name=None, **kwargs):
        super().__init__()
        self.name = name
        self.new_name = new_name

    def execute(self):
        if not self.name or not self.new_name:
            return {"code": 400, "body": {"status": "error",
                                          "message": "name and new_name are required"}}

        renamed = UPLOADS.rename_album(self.name, self.new_name)
        if renamed is None:
            return {"code": 400, "body": {"status": "error",
                                          "message": "could not rename album (missing, protected, or target exists)"}}

        try:
            active = CONFIG.get("wallpaper", "uploads_album", "Default")
            if active == self.name:
                CONFIG.set("wallpaper", "uploads_album", renamed)
                from services.wallpaper.wallpaper import WALLPAPER_SERVICE
                if WALLPAPER_SERVICE.repo == "My Uploads":
                    WALLPAPER_SERVICE.restart()
        except Exception as e:
            PIHOME_LOGGER.error("RenameAlbumEvent: active-album update failed: {}".format(e))

        return {"code": 200, "body": {"status": "success", "name": renamed}}

    def to_json(self):
        return json.dumps({"type": self.type, "name": self.name, "new_name": self.new_name})
