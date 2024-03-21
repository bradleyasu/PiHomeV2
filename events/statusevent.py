
import json
from events.pihomeevent import PihomeEvent

class StatusEvent(PihomeEvent):
    type = "status"
    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        return {
            "code": 200,
            "body": self.status_body()
        }

    def status_body(self):
        from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
        from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
        from services.audio.audioplayernew import AUDIO_PLAYER
        from services.taskmanager.taskmanager import TASK_MANAGER
        from services.weather.weather import WEATHER
        from services.wallpaper.wallpaper import WALLPAPER_SERVICE

        # TODO: Eventually have each service have a get_status method (or to_json)
        return {
            "type": "status",
            "status": "online",
            "wallpaper": {
                "current": WALLPAPER_SERVICE.current,
                "source": WALLPAPER_SERVICE.source,
                "allow_stretch": WALLPAPER_SERVICE.allow_stretch
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
                "is_paused": AUDIO_PLAYER.paused,
                "title": AUDIO_PLAYER.title,
                "percent": AUDIO_PLAYER.percent,
                "volume": AUDIO_PLAYER.volume,
                "playlist_pos": AUDIO_PLAYER.playlist_pos,
                "playlist_start": AUDIO_PLAYER.playlist_start,
                "queue": AUDIO_PLAYER.queue,
                "album_art": AUDIO_PLAYER.album_art,
                "state": AUDIO_PLAYER.current_state
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
            

    def to_json(self):
        return json.dumps({
            "type": self.type
        }
    )

    def to_definition(self):
        return {
            "type": self.type
        }