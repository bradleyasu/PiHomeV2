

import json
from util.const import _MUSIC_SCREEN
from util.helpers import audio_player, get_app, goto_screen
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
            result["type"] = "command"
            await socket.send(json.dumps(result))

        if message["type"] == "wallpaper_shuffle":
            get_app().wallpaper_service.shuffle()

        if message["type"] == "screen":
            goto_screen(message["screen"])
        
        if message["type"] == "audio":
            # check if play_url key exists
            if "play_url" in message:
                audio_player().play(message["play_url"])
                goto_screen(_MUSIC_SCREEN)
            if "volume" in message:
                audio_player().set_volume(message["volume"])
            if "stop" in message:
                audio_player().stop()
            if "next" in message:
                audio_player().next()
            if "prev" in message:
                audio_player().prev()
            if "clear_queue" in message:
                audio_player().clear_playlist()
            
            await socket.send(json.dumps({ 
                "type": "audio",
                "is_playing": get_app().audio_player.is_playing,
                "is_paused": get_app().audio_player.is_paused,
                "title": get_app().audio_player.title,
                "percent": get_app().audio_player.percent,
                "volume": get_app().audio_player.volume,
                "playlist_pos": get_app().audio_player.playlist_pos,
                "playlist_start": get_app().audio_player.playlist_start,
                "queue": get_app().audio_player.queue,
                "album_art": get_app().audio_player.album_art
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
                    "queue": get_app().audio_player.queue,
                    "album_art": get_app().audio_player.album_art
                },
                "timers":
                    list(map(lambda t: {
                        "label": t.timer.label,
                        "end_time": t.timer.end_time,
                        "duration": t.timer.duration,
                        "elapsed_time": t.timer.elapsed_time
                    }, get_app().timer_drawer.timer_widgets))
                ,
                "screens": {
                    "current": get_app().manager.current_screen.name,
                    "screens": list(map(lambda n: {
                        n: {
                            "label": get_app().screens[n].label,
                            "requires_pin": get_app().screens[n].requires_pin,
                            "hidden": get_app().screens[n].is_hidden,
                            "icon": get_app().screens[n].icon
                        }
                    }, get_app().screens))
                }
            }
            await socket.send(json.dumps(status))
