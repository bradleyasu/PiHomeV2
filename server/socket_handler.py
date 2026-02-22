

import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEventFactory
# PIHOME_SCREEN_MANAGER import removed - was unused
from services.audio.audioplayernew import AUDIO_PLAYER
from services.taskmanager.taskmanager import TASK_MANAGER
from services.wallpaper.wallpaper import WALLPAPER_SERVICE
from services.weather.weather import WEATHER
from util.const import _MUSIC_SCREEN
from util.helpers import get_app
from util.tools import execute_command


class SocketHandler():
    def __init__(self, **kwargs):
        super(SocketHandler, self).__init__(**kwargs)

    async def handle_message(self, message, socket):
        # TODO ALL of these need to be converted into PiHome Events and then executed
        if message == None:
            return
        message = json.loads(message)

        if "type" not in message:
            return

        event = PihomeEventFactory.create_event_from_dict(message)
        try:
            response = event.execute()
            await socket.send(json.dumps(response["body"]))
        except Exception as e:
            await socket.send(json.dumps({"status": "error", "message": "Failed to execute event", "error": str(e)}))
        


