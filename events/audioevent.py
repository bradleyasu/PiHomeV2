
import json
from events.pihomeevent import PihomeEvent
from services.audio.audioplayernew import AUDIO_PLAYER


class AudioEvent(PihomeEvent):
    type = "audio"
    def __init__(self, action = None, value = None, **kwargs):
        super().__init__()
        self.action = action
        self.value = value

    def execute(self):
        if self.action is None:
            return {
                "code": 400,
                "body": {"status": "error", "message": "No audio action provided"}
            }
        switcher = {
            "play_url": AUDIO_PLAYER.play,
            "play": AUDIO_PLAYER.play,
            "volume": AUDIO_PLAYER.set_volume,
            "stop": AUDIO_PLAYER.stop,
            "next": AUDIO_PLAYER.next,
            "prev": AUDIO_PLAYER.prev,
            "previous": AUDIO_PLAYER.prev,
            "clear_queue": AUDIO_PLAYER.clear_playlist,
            "save_url": AUDIO_PLAYER.add_saved_url_from_json,
            "save": AUDIO_PLAYER.add_saved_url_from_json,
            "save_current": AUDIO_PLAYER.add_save_current_from_json
        }
        if self.action in switcher:
            if self.value is not None:
                switcher[self.action](self.value)
            else:
                switcher[self.action]()
            return {
                "code": 200,
                "body": {"status": "success", "message": "Audio action executed successfully. Action: {} Value: {}".format(self.action, self.value)}
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

    def to_definition(self):
        return {
            "type": self.type,
            "action": self.type_def("string"),
            "value": self.type_def("string", False)
        }