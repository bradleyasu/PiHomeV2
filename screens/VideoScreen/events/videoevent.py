"""Events that drive the VideoScreen.

``video``              -- resolve a source and play it full screen
``video_stop``         -- stop playback and return to the previous screen
``video_update_ytdlp`` -- self-update yt-dlp

The last one exists because YouTube changes break extraction every few weeks
and the Pi is a kiosk: without it, fixing playback means finding a keyboard.
"""

import json
import threading

from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from util.const import _VIDEO_SCREEN
from util.phlog import PIHOME_LOGGER

try:
    # Reuse the existing `aplay -l` parser so the audio device dropdown offered
    # here matches the one the aplay event already offers.
    from events.aplayevent import _discover_devices
except Exception:  # pragma: no cover
    def _discover_devices():
        return []


def _as_int(value, default=0):
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value, default=False):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class VideoEvent(PihomeEvent):
    type = "video"

    def __init__(self, url, audio_device=None, quality=None, timeout=0, loop=False, **kwargs):
        super().__init__()
        self.url = (url or "").strip()
        self.audio_device = (audio_device or "").strip()
        self.quality = _as_int(quality, 0)
        self.timeout = _as_int(timeout, 0)
        self.loop = _as_bool(loop, False)

    def execute(self):
        if not self.url:
            return {
                "code": 400,
                "body": {"status": "error", "message": "url is required"}
            }

        try:
            screen = PIHOME_SCREEN_MANAGER.get_screen(_VIDEO_SCREEN)
        except Exception as e:
            PIHOME_LOGGER.error("VideoEvent: screen unavailable: {}".format(e))
            return {
                "code": 500,
                "body": {"status": "error", "message": "Video screen not loaded"}
            }

        screen.source = self.url
        screen.audio_device = self.audio_device
        screen.timeout = self.timeout
        screen.loop = self.loop
        screen.max_height_override = self.quality
        PIHOME_SCREEN_MANAGER.goto(_VIDEO_SCREEN)

        # Returns as soon as the screen is up. Resolving the source is network
        # work that happens on the screen's own worker thread, so an HTTP or
        # MQTT caller is never left waiting on yt-dlp.
        return {
            "code": 200,
            "body": {"status": "success", "message": "Playing {}".format(self.url)}
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "url": self.url,
            "audio_device": self.audio_device,
            "quality": self.quality,
            "timeout": self.timeout,
            "loop": self.loop,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "url": self.type_def(
                "string", True,
                "YouTube (or any yt-dlp site) link, direct media URL, or a file path on the Pi"
            ),
            "audio_device": self.type_def(
                "option", False,
                "ALSA output device for this video's audio (defaults to [video] audio_device)",
                _discover_devices()
            ),
            "quality": self.type_def(
                "integer", False,
                "Max video height in pixels. Defaults to 480, which matches the panel; "
                "higher costs decode budget on a Pi 3B without adding visible detail"
            ),
            "timeout": self.type_def(
                "integer", False, "Stop and go back after this many seconds (0 = play to the end)"
            ),
            "loop": self.type_def("boolean", False, "Repeat the video until stopped"),
        }


class VideoStopEvent(PihomeEvent):
    type = "video_stop"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        try:
            screen = PIHOME_SCREEN_MANAGER.get_screen(_VIDEO_SCREEN)
        except Exception:
            return {
                "code": 500,
                "body": {"status": "error", "message": "Video screen not loaded"}
            }
        if not screen.is_open:
            return {
                "code": 200,
                "body": {"status": "success", "message": "Nothing playing"}
            }
        screen.stop_playback()
        return {
            "code": 200,
            "body": {"status": "success", "message": "Playback stopped"}
        }

    def to_json(self):
        return json.dumps({"type": self.type})

    def to_definition(self):
        return {"type": self.type}


class VideoUpdateYtdlpEvent(PihomeEvent):
    type = "video_update_ytdlp"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        # yt-dlp -U can take a while; run it off the main thread and report
        # through a toast rather than holding the caller open.
        def _run():
            from screens.VideoScreen.resolver import update_ytdlp
            from util.configuration import CONFIG
            from util.helpers import toast
            path = CONFIG.get("video", "ytdlp_path", "yt-dlp").strip() or "yt-dlp"
            ok, message = update_ytdlp(ytdlp=path)
            PIHOME_LOGGER.info("VideoScreen: yt-dlp update: {}".format(message))
            try:
                toast(message, "success" if ok else "error", 5)
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True, name="videoscreen-ytdlp-update").start()
        return {
            "code": 200,
            "body": {"status": "success", "message": "Updating yt-dlp in the background"}
        }

    def to_json(self):
        return json.dumps({"type": self.type})

    def to_definition(self):
        return {"type": self.type}
