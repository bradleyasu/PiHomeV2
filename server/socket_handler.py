

import json
from util.helpers import get_app
from util.tools import execute_command


class SocketHandler():
    def __init__(self, **kwargs):
        super(SocketHandler, self).__init__(**kwargs)

    async def handle_message(self, message, socket):
        if message == None:
            return
        message = json.loads(message)
        if message["type"] == "command":
            command = message["command"]
            result = execute_command(command)
            await socket.send(json.dumps(result))
        
        if message["type"] == "status":
            status = {
                "status": "online",
                "wallpaper": {
                    "current": get_app().wallpaper_service.current,
                    "source": get_app().wallpaper_service.source,
                    "allow_stretch": get_app().wallpaper_service.allow_stretch
                },
                "weather": {
                    "weather_code": get_app().weather.weather_code,
                    "temperature": get_app().weather.temperature,
                    "humidity": get_app().weather.humidity,
                    "uv_index": get_app().weather.uv_index,
                    "wind_speed": get_app().weather.wind_speed,
                    "precip_propability": get_app().weather.precip_propability,
                    "future": get_app().weather.future
                }, 
                "audio": {
                    "is_playing": get_app().audio_player.is_playing,
                    "is_paused": get_app().audio_player.is_paused,
                    "title": get_app().audio_player.title,
                    "percent": get_app().audio_player.percent,
                    "volume": get_app().audio_player.volume,
                    "playlist_pos": get_app().audio_player.playlist_pos,
                    "playlist_start": get_app().audio_player.playlist_start,
                    "queue": get_app().audio_player.queue
                }
            }
            await socket.send(json.dumps(status))
