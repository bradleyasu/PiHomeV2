
import json
import os

from events.pihomeevent import PihomeEvent
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from util.phlog import PIHOME_LOGGER

_SCREENS_DIR = "./screens/"


def _screen_options():
    """Map of screen id -> label for every visible screen, for the event builder.

    Prefers the live screen manager (already sorted by menu index, with disabled
    screens excluded), and falls back to reading the manifests off disk so
    introspection still works before the screens have been loaded.
    """
    options = {}
    for screen_id, screen in getattr(PIHOME_SCREEN_MANAGER, "loaded_screens", {}).items():
        if getattr(screen, "is_hidden", False):
            continue
        options[screen_id] = getattr(screen, "label", "") or screen_id
    if options:
        return options
    return _options_from_manifests()


def _options_from_manifests():
    """Read screens/*/manifest.json directly, skipping disabled and hidden screens."""
    found = []
    for root, dirs, files in os.walk(_SCREENS_DIR):
        if "manifest.json" not in files:
            continue
        try:
            with open(os.path.join(root, "manifest.json"), "r") as manifest:
                metadata = json.load(manifest)
        except Exception as e:
            PIHOME_LOGGER.error("app: could not read manifest in {}: {}".format(root, e))
            continue
        if metadata.get("disabled") or metadata.get("hidden"):
            continue
        screen_id = metadata.get("id")
        if not screen_id:
            continue
        found.append((metadata.get("index", 9999), screen_id, metadata.get("label") or screen_id))
    return {screen_id: label for _, screen_id, label in sorted(found, key=lambda item: item[0])}


class AppEvent(PihomeEvent):
    type = "app"
    def __init__(self, app, **kwargs):
        super().__init__()
        self.app = app

    def execute(self):
        if self.app not in getattr(PIHOME_SCREEN_MANAGER, "loaded_screens", {}):
            return {
                "code": 404,
                "body": {"status": "error", "message": "Unknown app \"{}\"".format(self.app)}
            }
        PIHOME_SCREEN_MANAGER.goto(self.app)
        return {
            "code": 200,
            "body": {"status": "success", "message": "App launched"}
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "app": self.app
        }
    )

    def to_definition(self):
        return {
            "type": self.type,
            "app": self.type_def("option", True, "Screen to launch", _screen_options())
        }
