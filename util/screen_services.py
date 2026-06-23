"""Per-screen background service discovery and startup.

A screen may ship its own background services under ``screens/<Name>/services/``
and declare them in its ``manifest.json`` via a ``services`` array of module names
(without the ``.py`` extension), e.g.::

    "services": ["emporia_service"]

At startup PiHome scans every (non-disabled) manifest and imports each declared
service module, which starts that service. This keeps a service drop-in with its
screen: remove the screen directory and its service goes with it, with no edits to
``main.py``.

A PiHome service is an informal **module-level singleton** that self-starts a
daemon thread in ``__init__`` (the module exports e.g. ``EMPORIA_SERVICE =
EmporiaService()``). The screen and its event handlers import that same instance by
package path.

This loader imports via :func:`importlib.import_module` using the full dotted
package path (``screens.<Name>.services.<mod>``) — NOT ``spec_from_file_location``
— so the module is registered in ``sys.modules`` and the loader, the screen, and
the screen's event handlers all share the **one** singleton instance. Loading the
same module via a file spec would create a second module object (and therefore a
second singleton, second thread, second cache writer).

Mirrors ``util/dependencies.py``: same manifest-scan style, Kivy-free at module
scope, and tolerant of malformed manifests / failed imports (a broken or
missing-dependency service is logged and skipped rather than aborting startup).
"""

import glob
import importlib
import inspect
import json

from util.phlog import PIHOME_LOGGER

_MANIFEST_GLOB = "./screens/*/manifest.json"

# Discovered service instances that expose a shutdown()/stop() hook, so on_stop()
# can tear them down explicitly. Services without such a method rely on their
# daemon threads dying with the process.
LOADED_SERVICES = []


def _iter_screen_manifests():
    """Yield ``(screen_dir, manifest_dict)`` for every non-disabled screen.

    Mirrors the glob-based manifest walk in ``util/dependencies.py``. Malformed or
    unreadable manifests are logged and skipped rather than aborting the scan.
    """
    for path in sorted(glob.glob(_MANIFEST_GLOB)):
        try:
            with open(path, "r") as f:
                manifest = json.load(f)
        except Exception as e:
            PIHOME_LOGGER.error(f"ScreenServices: failed to read {path}: {e}")
            continue
        if manifest.get("disabled"):
            continue
        # screen_dir is the directory name, e.g. ./screens/EmporiumPower/manifest.json -> EmporiumPower
        screen_dir = path.replace("\\", "/").split("/")[-2]
        yield screen_dir, manifest


def _register_shutdownable(module):
    """Record any module-level service instance exposing shutdown()/stop()."""
    for _, obj in inspect.getmembers(module):
        if inspect.isclass(obj) or inspect.ismodule(obj):
            continue
        if callable(getattr(obj, "shutdown", None)) or callable(getattr(obj, "stop", None)):
            if obj not in LOADED_SERVICES:
                LOADED_SERVICES.append(obj)


def load_screen_services():
    """Import every screen-declared service so it starts at boot.

    Importing the module triggers the service's self-starting singleton. The import
    is idempotent: if the screen module already imported the service at top level,
    ``import_module`` returns the cached module and no second singleton is created.
    """
    for screen_dir, manifest in _iter_screen_manifests():
        services = manifest.get("services") or []
        if not isinstance(services, list):
            PIHOME_LOGGER.error(
                f"ScreenServices: '{screen_dir}' manifest 'services' is not a list — skipping"
            )
            continue
        for entry in services:
            dotted = f"screens.{screen_dir}.services.{entry}"
            try:
                module = importlib.import_module(dotted)
                _register_shutdownable(module)
                PIHOME_LOGGER.info(f"ScreenServices: started {dotted}")
            except Exception as e:
                # A service whose pip dependency isn't installed yet (or any other
                # import error) must not abort startup — the dep auto-installer +
                # restart will make it available on a later boot, and well-behaved
                # services degrade gracefully when their dependency is absent.
                PIHOME_LOGGER.error(f"ScreenServices: failed to start {dotted}: {e}")


def shutdown_screen_services():
    """Tear down discovered services that expose a shutdown()/stop() hook."""
    for svc in LOADED_SERVICES:
        try:
            hook = getattr(svc, "shutdown", None) or getattr(svc, "stop", None)
            if callable(hook):
                hook()
        except Exception as e:
            PIHOME_LOGGER.error(f"ScreenServices: shutdown failed for {svc!r}: {e}")
