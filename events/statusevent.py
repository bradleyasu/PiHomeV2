
import json
from events.pihomeevent import PihomeEvent
from util.tools import get_cpu_temp

class StatusEvent(PihomeEvent):
    type = "status"
    def __init__(self, depth = "base", **kwargs):
        super().__init__()
        self.depth = depth

    def execute(self):
        return {
            "code": 200,
            "body": self.status_body()
        }

    def status_body(self):
        if self.depth == "advanced":
            return self.return_advanced()
        else:
            return self.return_base()

    def return_advanced(self):
        data = self.return_base()
        return data

    def return_base(self):
        from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
        from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
        from services.taskmanager.taskmanager import TASK_MANAGER
        from services.weather.weather import WEATHER
        from services.wallpaper.wallpaper import WALLPAPER_SERVICE
        from services.airplay.airplay import AIRPLAY
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
            "now_playing": {
                "is_playing": AIRPLAY.is_playing,
                "title": AIRPLAY.title,
                "artist": AIRPLAY.artist,
                "album": AIRPLAY.album,
                "has_artwork": AIRPLAY.cover_art_bytes is not None
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