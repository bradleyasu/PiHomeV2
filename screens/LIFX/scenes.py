"""LIFX scenes - local snapshots and imported LIFX Cloud scenes.

No Kivy.  ``requests`` is imported inside :class:`LifxCloud` methods so this
module stays importable under a bare ``python3``::

    python3 screens/LIFX/tests/test_scenes.py

There is no scene concept in the LAN protocol - scenes live in the LIFX Cloud.
But ``GET /v1/scenes`` returns each scene's full ``states[]`` array, so rather
than round-tripping through ``PUT /v1/scenes/.../activate`` (~800ms, rate
limited, and dead when the bulbs' cloud link is down) we cache those states and
replay them over the LAN in ~15ms.  That also means a cloud scene and a local
snapshot are the same thing by the time anything applies one: a list of
``(serial, HSBK, power)``.

Stored shape, shared by both sources::

    {"id", "name", "source": "local"|"cloud", "updated_at": float,
     "states": [{"selector", "hue", "saturation", "brightness", "kelvin",
                 "power"}]}

Colour values are user units (hue 0-360, saturation/brightness 0-100, kelvin
in K), which keeps the JSON legible and converts on demand.
"""

import json
import os
import time
import uuid

from screens.LIFX.protocol import (
    U16,
    clamp_kelvin,
    hsbk_from_pct,
)

# Module level so tests can point it at a temp file.
SCENES_FILE = "cache/lifx_scenes.json"

SOURCE_LOCAL = "local"
SOURCE_CLOUD = "cloud"

CLOUD_BASE = "https://api.lifx.com/v1"


class SceneStore(object):
    """Persisted scenes, local and imported."""

    def __init__(self, path=None):
        self.path = path or SCENES_FILE
        self._scenes = self._load()

    # ── persistence ──

    def _load(self):
        try:
            with open(self.path, "r") as handle:
                raw = json.load(handle)
        except (FileNotFoundError, ValueError, OSError):
            return {}
        if not isinstance(raw, dict):
            return {}
        scenes = {}
        for sid, scene in raw.items():
            if isinstance(scene, dict) and scene.get("states"):
                scene.setdefault("id", sid)
                scene.setdefault("source", SOURCE_LOCAL)
                scene.setdefault("name", sid)
                scene.setdefault("updated_at", 0.0)
                scenes[str(sid)] = scene
        return scenes

    def _save(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w") as handle:
            json.dump(self._scenes, handle, indent=2, sort_keys=True)

    def reload(self):
        self._scenes = self._load()

    # ── reads ──

    def list(self):
        """Local scenes first (they always work), then cloud, each by name."""
        return sorted(
            (dict(scene) for scene in self._scenes.values()),
            key=lambda s: (s.get("source") != SOURCE_LOCAL,
                           (s.get("name") or "").lower()),
        )

    def get(self, name_or_id):
        """Exact id, else case-insensitive name.  -> scene dict or None."""
        if not name_or_id:
            return None
        key = str(name_or_id).strip()
        if key in self._scenes:
            return dict(self._scenes[key])
        lowered = key.lower()
        for scene in self.list():        # list() orders local before cloud
            if (scene.get("name") or "").strip().lower() == lowered:
                return scene
        return None

    # ── writes ──

    def save_snapshot(self, name, registry, serials=None):
        """Capture the current state of *serials* (or everything) as a scene.

        Replaces any existing local scene with the same name so re-saving is
        the obvious way to update one.
        """
        name = (name or "").strip()
        if not name:
            raise ValueError("Scene name is required")

        chosen = list(serials) if serials else list(registry.keys())
        states = []
        for serial in chosen:
            entry = registry.get(serial)
            if not entry:
                continue
            states.append({
                "selector": "id:{}".format(serial),
                "hue": round((entry.get("hue", 0) or 0) / float(U16) * 360.0, 2),
                "saturation": round(
                    (entry.get("saturation", 0) or 0) / float(U16) * 100.0, 2),
                "brightness": round(
                    (entry.get("brightness", 0) or 0) / float(U16) * 100.0, 2),
                "kelvin": clamp_kelvin(entry.get("kelvin", 3500)),
                "power": bool(entry.get("power")),
            })

        if not states:
            raise ValueError("No bulbs to capture")

        existing = None
        for sid, scene in self._scenes.items():
            if (scene.get("source") == SOURCE_LOCAL
                    and (scene.get("name") or "").strip().lower() == name.lower()):
                existing = sid
                break

        sid = existing or "local:{}".format(uuid.uuid4().hex[:12])
        scene = {
            "id": sid,
            "name": name,
            "source": SOURCE_LOCAL,
            "updated_at": time.time(),
            "states": states,
        }
        self._scenes[sid] = scene
        self._save()
        return dict(scene)

    def remove(self, sid):
        scene = self.get(sid)
        if scene is None:
            return False
        self._scenes.pop(scene["id"], None)
        self._save()
        return True

    def merge_cloud(self, cloud_scenes):
        """Upsert imported scenes by their cloud id.  Local scenes are untouched.

        Cloud scenes that vanished upstream are dropped, so deleting one in the
        LIFX app eventually removes it here too.  -> number of scenes stored.
        """
        normalized = []
        for raw in cloud_scenes or []:
            scene = normalize_cloud_scene(raw)
            if scene is not None:
                normalized.append(scene)

        keep = {scene["id"] for scene in normalized}
        for sid in list(self._scenes):
            if self._scenes[sid].get("source") == SOURCE_CLOUD and sid not in keep:
                self._scenes.pop(sid)

        for scene in normalized:
            self._scenes[scene["id"]] = scene

        self._save()
        return len(normalized)


# ── Cloud ─────────────────────────────────────────────────────────────────

def normalize_cloud_scene(raw):
    """A ``GET /v1/scenes`` entry -> our stored shape, or None if unusable."""
    if not isinstance(raw, dict):
        return None
    uuid_ = raw.get("uuid") or raw.get("id")
    name = (raw.get("name") or "").strip()
    if not uuid_ or not name:
        return None

    states = []
    for state in raw.get("states") or []:
        if not isinstance(state, dict):
            continue
        selector = (state.get("selector") or "").strip()
        if not selector:
            continue
        color = state.get("color") or {}
        power = state.get("power")
        # The cloud reports saturation and brightness as 0-1 fractions.
        states.append({
            "selector": selector,
            "hue": float(color.get("hue") or 0.0) % 360.0,
            "saturation": _fraction_to_pct(color.get("saturation")),
            "brightness": _fraction_to_pct(
                state.get("brightness", color.get("brightness"))),
            "kelvin": clamp_kelvin(color.get("kelvin") or 3500),
            "power": str(power).lower() != "off" if power is not None else True,
        })

    if not states:
        return None

    return {
        "id": str(uuid_),
        "name": name,
        "source": SOURCE_CLOUD,
        "updated_at": float(raw.get("updated_at") or time.time()),
        "states": states,
    }


def _fraction_to_pct(value):
    if value is None:
        return 100.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 100.0
    return round(max(0.0, min(100.0, number * 100.0)), 2)


class LifxCloud(object):
    """Thin read client for the LIFX Cloud scene list.

    Used only to *import* scenes; applying them happens over the LAN.
    """

    BASE = CLOUD_BASE

    def __init__(self, token=""):
        self.token = (token or "").strip()

    @property
    def available(self):
        if not self.token:
            return False
        try:
            import requests  # noqa: F401
        except ImportError:
            return False
        return True

    def _headers(self):
        return {"Authorization": "Bearer {}".format(self.token)}

    def list_scenes(self, timeout=10):
        """-> list of scenes in our stored shape.  Raises on transport/auth failure."""
        if not self.token:
            raise RuntimeError("No LIFX Cloud token configured")
        import requests

        response = requests.get("{}/scenes".format(self.BASE),
                                headers=self._headers(), timeout=timeout)
        if response.status_code == 401:
            raise RuntimeError("LIFX Cloud rejected the token")
        response.raise_for_status()

        scenes = []
        for raw in response.json() or []:
            scene = normalize_cloud_scene(raw)
            if scene is not None:
                scenes.append(scene)
        return scenes

    def activate(self, scene_uuid, duration=1.0, timeout=10):
        """Cloud-side activation.  Only a fallback for unresolvable selectors."""
        if not self.token:
            raise RuntimeError("No LIFX Cloud token configured")
        import requests

        response = requests.put(
            "{}/scenes/scene_id:{}/activate".format(self.BASE, scene_uuid),
            headers=self._headers(), json={"duration": float(duration)},
            timeout=timeout)
        response.raise_for_status()
        return True


# ── Applying a scene over the LAN ─────────────────────────────────────────

def resolve_scene_states(scene, registry):
    """Map a scene's selectors onto discovered bulbs.

    -> ``([(serial, (h, s, b, k), power_on), ...], [unresolved_selector, ...])``
    where the HSBK tuple is raw u16, ready for ``client.set_color``.

    Later states win when selectors overlap, matching how the LIFX app layers a
    broad selector under a specific one.
    """
    applies = {}
    unresolved = []

    for state in (scene or {}).get("states") or []:
        selector = (state.get("selector") or "").strip()
        serials = _match_selector(selector, registry)
        if not serials:
            unresolved.append(selector)
            continue

        hsbk = hsbk_from_pct(
            state.get("hue", 0.0) or 0.0,
            state.get("saturation", 0.0) or 0.0,
            state.get("brightness", 100.0) if state.get("brightness") is not None else 100.0,
            state.get("kelvin", 3500) or 3500,
        )
        power = bool(state.get("power", True))
        for serial in serials:
            applies[serial] = (serial, hsbk, power)

    ordered = [applies[s] for s in sorted(applies)]
    return ordered, unresolved


def _match_selector(selector, registry):
    """LIFX selector syntax -> matching serials."""
    if not selector:
        return []

    lowered = selector.lower()
    if lowered in ("all", "*"):
        return sorted(registry)

    if ":" not in lowered:
        # A bare selector is treated as a label, which is what the app shows.
        return _match_field(registry, "label", selector)

    kind, _, value = selector.partition(":")
    kind = kind.strip().lower()
    value = value.strip()

    if kind == "id":
        serial = value.lower()
        return [serial] if serial in registry else []
    if kind == "group_id":
        return _match_field(registry, "group_id", value)
    if kind == "group":
        return _match_field(registry, "group", value)
    if kind == "location_id":
        return _match_field(registry, "location_id", value)
    if kind == "location":
        return _match_field(registry, "location", value)
    if kind == "label":
        return _match_field(registry, "label", value)
    return []


def _match_field(registry, field, value):
    wanted = (value or "").strip().lower()
    if not wanted:
        return []
    return sorted(serial for serial, entry in registry.items()
                  if (entry.get(field) or "").strip().lower() == wanted)


def scene_swatches(scene, limit=4):
    """A few representative RGB colours for a scene card.  -> [(r, g, b), ...]"""
    from screens.LIFX.protocol import hsbk_to_rgb

    swatches = []
    for state in (scene or {}).get("states") or []:
        if not state.get("power", True):
            continue
        hsbk = hsbk_from_pct(
            state.get("hue", 0.0) or 0.0,
            state.get("saturation", 0.0) or 0.0,
            state.get("brightness", 100.0) if state.get("brightness") is not None else 100.0,
            state.get("kelvin", 3500) or 3500,
        )
        swatches.append(hsbk_to_rgb(*hsbk))
        if len(swatches) >= limit:
            break
    return swatches
