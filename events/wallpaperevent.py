import json
from events.pihomeevent import PihomeEvent
from services.wallpaper.wallpaper import WALLPAPER_SERVICE


class WallpaperEvent(PihomeEvent):
    type = "wallpaper"
    
    def __init__(self, action, value = None, **kwargs):
        super().__init__()
        self.action = action
        self.value = value

    def execute(self):
        switcher = {
            "shuffle": WALLPAPER_SERVICE.shuffle
        }

        if self.action in switcher:
            switcher[self.action]()
            return {
                "code": 200,
                "body": {"status": "success", "message": "Wallpaper action executed successfully"}
            }
        else:
            return {
                "code": 400,
                "body": {"status": "error", "message": "Invalid wallpaper action", "valid_actions": list(switcher.keys())}
            }


    def to_json(self):
        return json.dumps({
            "type": self.type,
            "action": self.action,
            "value": self.value
    })
