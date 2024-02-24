
import json
from events.pihomeevent import PihomeEvent
from services.audio.audioplayer import AUDIO_PLAYER


class AudioEvent(PihomeEvent):
    type = "audio"
    def __init__(self, action, value, **kwargs):
        super().__init__()
        self.action = action
        self.value = value

    def execute(self):
        switcher = {
            "play_url": AUDIO_PLAYER.play,
            "volume": AUDIO_PLAYER.set_volume,
            "stop": AUDIO_PLAYER.stop,
            "next": AUDIO_PLAYER.next,
            "prev": AUDIO_PLAYER.prev,
            "clear_queue": AUDIO_PLAYER.clear_playlist
        }
        if self.action in switcher:
            switcher[self.action](self.value)
            return {
                "code": 200,
                "body": {"status": "success", "message": "App launched"}
            }
        else:
            return {
                "code": 400,
                "body": {"status": "error", "message": "Invalid audio action", "valid_actions": list(switcher.keys())}
            }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "action": self.action,
            "value": self.value
        }
    )