"""Scene management events: ``lifx_scenes``, ``lifx_scene_save``,
``lifx_scene_remove``.

Three small classes in one file - the event factory discovers by class
introspection, not by filename, so there is no reason to split them.

Applying a scene is not here: that is ``{"type": "lifx", "scene": "..."}``.
"""

from events.pihomeevent import PihomeEvent
from screens.LIFX.targeting import TargetError

try:
    from screens.LIFX.services.lifx_service import LIFX_SERVICE
except ImportError:
    LIFX_SERVICE = None


def _unavailable():
    return {"code": 503, "body": {
        "status": "error", "error_code": "no_devices",
        "message": "The LIFX screen is not installed"}}


def _summarize(scene):
    return {
        "id": scene["id"],
        "name": scene["name"],
        "source": scene.get("source", "local"),
        "bulbs": len(scene.get("states") or []),
    }


class LifxScenesEvent(PihomeEvent):
    """List every scene, local snapshots and imported LIFX app scenes alike."""

    type = "lifx_scenes"

    def __init__(self, **kwargs):
        super().__init__()

    def execute(self):
        if LIFX_SERVICE is None:
            return _unavailable()
        scenes = [_summarize(s) for s in LIFX_SERVICE.list_scenes()]
        return {"code": 200, "body": {
            "status": "success",
            "message": "{} scene(s)".format(len(scenes)),
            "scenes": scenes,
        }}

    def to_definition(self):
        return {"type": self.type}


class LifxSceneSaveEvent(PihomeEvent):
    """Capture the current state of some or all bulbs as a local scene."""

    type = "lifx_scene_save"

    def __init__(self, name=None, target=None, overwrite=None, **kwargs):
        super().__init__()
        self.name = name
        self.target = target
        self.overwrite = overwrite

    def execute(self):
        if LIFX_SERVICE is None:
            return _unavailable()

        name = (self.name or "").strip()
        if not name:
            return {"code": 400, "body": {
                "status": "error", "error_code": "bad_request",
                "message": "name is required"}}

        overwrite = str(self.overwrite).strip().lower() in ("1", "true", "yes")
        existing = LIFX_SERVICE.get_scene(name)
        if existing is not None and not overwrite:
            if existing.get("source") == "cloud":
                message = ("'{}' is a LIFX app scene. Pick another name, or pass "
                           "overwrite to shadow it with a local one.".format(name))
            else:
                message = "A scene named '{}' already exists. Pass overwrite to " \
                          "replace it.".format(name)
            return {"code": 409, "body": {
                "status": "error", "error_code": "scene_exists",
                "message": message, "id": existing["id"]}}

        serials = None
        if self.target:
            try:
                serials, _kind, _label = LIFX_SERVICE.resolve(self.target)
            except TargetError as exc:
                return {"code": exc.code, "body": {
                    "status": "error", "error_code": exc.error_code,
                    "message": exc.message}}

        try:
            scene = LIFX_SERVICE.save_scene(name, serials)
        except ValueError as exc:
            return {"code": 400, "body": {
                "status": "error", "error_code": "bad_request",
                "message": str(exc)}}

        return {"code": 200, "body": {
            "status": "success",
            "message": "Saved scene '{}' with {} bulb(s)".format(
                scene["name"], len(scene["states"])),
            "scene": _summarize(scene),
            "id": scene["id"],
        }}

    def to_definition(self):
        return {
            "type": self.type,
            "name": self.type_def("string", True, "Name for the saved scene"),
            "target": self.type_def(
                "string", False,
                "Capture only this bulb or room. Defaults to every bulb."),
            "overwrite": self.type_def(
                "string", False, "Set to 1 to replace an existing scene"),
        }


class LifxSceneRemoveEvent(PihomeEvent):
    """Delete a saved scene.  An imported cloud scene comes back on the next sync."""

    type = "lifx_scene_remove"

    def __init__(self, id=None, **kwargs):
        super().__init__()
        self.id = id

    def execute(self):
        if LIFX_SERVICE is None:
            return _unavailable()

        key = (self.id or "").strip()
        if not key:
            return {"code": 400, "body": {
                "status": "error", "error_code": "bad_request",
                "message": "id is required"}}

        if not LIFX_SERVICE.remove_scene(key):
            return {"code": 404, "body": {
                "status": "error", "error_code": "scene_not_found",
                "message": "No LIFX scene '{}'".format(key)}}

        return {"code": 200, "body": {
            "status": "success", "message": "Removed scene '{}'".format(key)}}

    def to_definition(self):
        options = {}
        if LIFX_SERVICE is not None:
            for scene in LIFX_SERVICE.list_scenes():
                options[scene["id"]] = "{}  ({})".format(
                    scene["name"], scene.get("source", "local"))
        return {
            "type": self.type,
            "id": self.type_def("option", True, "Scene to remove", options),
        }
