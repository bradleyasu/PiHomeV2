"""Per-screen Python dependency detection and runtime auto-install.

Each screen's ``manifest.json`` may declare an optional ``dependencies`` array of
pip requirement strings (e.g. ``["zeroconf", "paho-mqtt==1.6.1"]``). At startup
PiHome scans every (non-disabled) manifest, installs any declared dependency that
isn't already present, and reports progress through the Notification Center.

The module intentionally avoids importing Kivy at module scope — all UI-touching
imports are deferred into function bodies (mirroring ``NotificationEvent``) so the
pure logic stays importable/unit-testable headlessly.
"""

import glob
import importlib.metadata
import json
import re
import subprocess
import sys
import threading
import time

from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

_MANIFEST_GLOB = "./screens/*/manifest.json"

# A freshly pip-installed package can't be adopted by the already-running process
# (modules that import it have already bound their fallbacks, and startup-service
# singletons hold stale references). The only reliable way to pick up a new
# dependency is a process restart, so after any successful install we surface a
# single batched restart prompt (or auto-restart, if configured).
_RESTART_NID = "depinstall_restart"
_RESTART_EVENT = {"type": "app", "app": "_shutdown"}


def _iter_screen_manifests():
    """Yield ``(screen_dir, manifest_dict)`` for every non-disabled screen.

    Mirrors the glob-based manifest walk in ``server/server.py``. Malformed or
    unreadable manifests are logged and skipped rather than aborting the scan.
    """
    for path in sorted(glob.glob(_MANIFEST_GLOB)):
        try:
            with open(path, "r") as f:
                manifest = json.load(f)
        except Exception as e:
            PIHOME_LOGGER.error(f"Dependencies: failed to read {path}: {e}")
            continue
        if manifest.get("disabled"):
            continue
        # screen_dir is the directory name, e.g. ./screens/Nanoleaf/manifest.json -> Nanoleaf
        screen_dir = path.replace("\\", "/").split("/")[-2]
        yield screen_dir, manifest


def _dist_name(requirement):
    """Extract the distribution name from a pip requirement string.

    ``"paho-mqtt==1.6.1"`` -> ``"paho-mqtt"``, ``"requests[socks]>=2"`` -> ``"requests"``.
    """
    return re.split(r"[<>=!~;\[ ]", requirement.strip(), maxsplit=1)[0].strip()


def _missing(requirements):
    """Return the subset of *requirements* that are not currently installed.

    Uses ``importlib.metadata`` (distribution name) rather than import so that
    pip-name/import-name mismatches (e.g. ``paho-mqtt`` -> ``paho.mqtt``) are
    handled correctly. Entries that begin with ``-`` are rejected outright to
    prevent pip option injection from an untrusted/dropped-in manifest.
    """
    missing = []
    for req in requirements:
        req = (req or "").strip()
        if not req:
            continue
        if req.startswith("-"):
            PIHOME_LOGGER.warn(f"Dependencies: rejecting suspicious requirement '{req}'")
            continue
        name = _dist_name(req)
        if not name:
            continue
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(req)
    return missing


def _pip_install(requirements):
    """Install *requirements* into the running interpreter.

    Adds ``--break-system-packages`` on Linux/Pi (PEP 668 externally-managed
    environments) and omits it elsewhere. Returns ``(ok, combined_output)``.
    """
    flags = []
    if sys.platform.startswith("linux"):
        flags.append("--break-system-packages")
    cmd = [sys.executable, "-m", "pip", "install", "--no-input", *flags, *requirements]
    PIHOME_LOGGER.debug(f"Dependencies: running {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
    except Exception as e:
        return False, str(e)
    return proc.returncode == 0, proc.stdout or ""


def _notify(nid, title, description, level, event=None):
    """Fire (or upsert, by id) a Notification Center entry. Best-effort.

    *event* is an optional PiHome event dict fired when the notification is tapped.
    """
    try:
        from events.notificationevent import NotificationEvent
        # execute_safe: this runs on the dependency worker thread, but the
        # notification center is a Kivy widget — marshal onto the main thread.
        NotificationEvent(
            title=title, description=description, level=level, id=nid, event=event
        ).execute_safe()
    except Exception as e:
        PIHOME_LOGGER.error(f"Dependencies: notification failed: {e}")


def _auto_restart_enabled():
    return CONFIG.get("dependencies", "auto_restart", "0").strip().lower() in ("1", "true")


def _request_restart():
    """Prompt for (or perform) a PiHome restart after new deps were installed."""
    if _auto_restart_enabled():
        _notify(
            _RESTART_NID,
            "Restarting PiHome",
            "New screen dependencies were installed. Restarting to apply...",
            "warning",
        )
        time.sleep(3)  # let the notification render/persist before we exit
        try:
            from events.rebootevent import RebootEvent
            RebootEvent(action="restart_pihome").execute_safe()
        except Exception as e:
            PIHOME_LOGGER.error(f"Dependencies: auto-restart failed: {e}")
    else:
        _notify(
            _RESTART_NID,
            "Restart required",
            "New screen dependencies were installed. Tap to restart PiHome and finish setup.",
            "warning",
            event=_RESTART_EVENT,
        )


def _check_and_install():
    """Worker body: scan manifests, install missing deps, report via notifications."""
    installed_any = False
    for screen_dir, manifest in _iter_screen_manifests():
        deps = manifest.get("dependencies") or []
        if not isinstance(deps, list) or not deps:
            continue
        missing = _missing(deps)
        if not missing:
            continue

        label = manifest.get("label", screen_dir)
        nid = "depinstall_" + screen_dir
        pkgs = ", ".join(missing)
        PIHOME_LOGGER.info(f"Dependencies: {label} missing {pkgs} - installing")
        _notify(
            nid,
            "Installing dependencies",
            f"{label}: installing {pkgs}...",
            "info",
        )

        ok, output = _pip_install(missing)
        if ok:
            installed_any = True
            PIHOME_LOGGER.info(f"Dependencies: {label} installed {pkgs}")
            _notify(
                nid,
                "Dependencies installed",
                f"{label}: dependencies installed.",
                "success",
            )
        else:
            PIHOME_LOGGER.error(f"Dependencies: {label} install failed:\n{output}")
            _notify(
                nid,
                "Dependency install failed",
                f"{label}: install failed. See logs.",
                "error",
            )

    # A new package can't be adopted by the running process — prompt/perform a
    # restart once, after all screens are handled (not per-screen).
    if installed_any:
        _request_restart()


def ensure_screen_dependencies(delay=30):
    """Kick off the dependency check on a daemon thread (non-blocking).

    Waits *delay* seconds first so PiHome is fully started and the Notification
    Center is mounted and able to receive notifications before the scan runs.
    """
    def _run():
        if delay:
            time.sleep(delay)
        _check_and_install()

    threading.Thread(target=_run, daemon=True, name="screen-dependencies").start()
