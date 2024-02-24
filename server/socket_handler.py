

import json
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from events.pihomeevent import PihomeEventFactory
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from services.audio.audioplayer import AUDIO_PLAYER
from services.taskmanager.taskmanager import TASK_MANAGER
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
        if "webhook" in message:
            payload = message["webhook"]
            if "type" in payload:
                event = PihomeEventFactory.create_event_from_dict(payload)
                event.execute()

        if "type" not in message:
            return

        if message["type"] == "command":
            command = message["command"]
            result = execute_command(command)
            result["type"] = "command"
            await socket.send(json.dumps(result))

        if message["type"] == "wallpaper_shuffle":
            get_app().wallpaper_service.shuffle()

        if message["type"] == "screen":
            PIHOME_SCREEN_MANAGER.goto(message["screen"])

        if message["type"] == "timer":
            TIMER_DRAWER.create_timer(message["duration"], message["label"])
        
        if message["type"] == "audio":
            # check if play_url key exists
            if "play_url" in message:
                AUDIO_PLAYER.play(message["play_url"])
                PIHOME_SCREEN_MANAGER.goto(_MUSIC_SCREEN)
            if "volume" in message:
                AUDIO_PLAYER.set_volume(message["volume"])
            if "stop" in message:
                AUDIO_PLAYER.stop()
            if "next" in message:
                AUDIO_PLAYER.next()
            if "prev" in message:
                AUDIO_PLAYER.prev()
            if "clear_queue" in message:
                AUDIO_PLAYER.clear_playlist()
            
            await socket.send(json.dumps({ 
                "type": "audio",
                "is_playing": AUDIO_PLAYER.is_playing,
                "is_paused": AUDIO_PLAYER.is_paused,
                "title": AUDIO_PLAYER.title,
                "percent": AUDIO_PLAYER.percent,
                "volume": AUDIO_PLAYER.volume,
                "playlist_pos": AUDIO_PLAYER.playlist_pos,
                "playlist_start": AUDIO_PLAYER.playlist_start,
                "queue": AUDIO_PLAYER.queue,
                "album_art": AUDIO_PLAYER.album_art
            }))
            

        if message["type"] == "status":
            status = {
                "type": "status",
                "status": "online",
                "wallpaper": {
                    "current": get_app().wallpaper_service.current,
                    "source": get_app().wallpaper_service.source,
                    "allow_stretch": get_app().wallpaper_service.allow_stretch
                },
                "weather": {
                    "weather_code": WEATHER.weather_code,
                    "temperature": WEATHER.temperature,
                    "humidity": WEATHER.humidity,
                    "uv_index": WEATHER.uv_index,
                    "wind_speed": WEATHER.wind_speed,
                    "precip_propability": WEATHER.precip_propability,
                    "future": WEATHER.future
                }, 
                "audio": {
                    "is_playing": AUDIO_PLAYER.is_playing,
                    "is_paused": AUDIO_PLAYER.is_paused,
                    "title": AUDIO_PLAYER.title,
                    "percent": AUDIO_PLAYER.percent,
                    "volume": AUDIO_PLAYER.volume,
                    "playlist_pos": AUDIO_PLAYER.playlist_pos,
                    "playlist_start": AUDIO_PLAYER.playlist_start,
                    "queue": AUDIO_PLAYER.queue,
                    "album_art": AUDIO_PLAYER.album_art
                },
                "timers":
                    list(map(lambda t: {
                        "label": t.timer.label,
                        "end_time": t.timer.end_time,
                        "duration": t.timer.duration,
                        "elapsed_time": t.timer.elapsed_time
                    }, TIMER_DRAWER.timer_widgets))
                ,
                "screens": {
                    "current": PIHOME_SCREEN_MANAGER.current_screen.name,
                    "screens": list(map(lambda n: {
                        n: {
                            "label": PIHOME_SCREEN_MANAGER.loaded_screens[n].label,
                            "requires_pin": PIHOME_SCREEN_MANAGER.loaded_screens[n].requires_pin,
                            "hidden": PIHOME_SCREEN_MANAGER.loaded_screens[n].is_hidden,
                            "icon": PIHOME_SCREEN_MANAGER.loaded_screens[n].icon
                        }
                    }, PIHOME_SCREEN_MANAGER.loaded_screens))
                },
                "tasks": TASK_MANAGER.tasks_to_json()
            }
            await socket.send(json.dumps(status))
