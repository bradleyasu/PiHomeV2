"""libmpv-backed video playback, rendered into a buffer the screen can blit.

Why libmpv rather than ffpyplayer (which BambuLab uses for its camera):

* **Two streams, no mux.** yt-dlp hands back a separate H.264 video URL and an
  AAC audio URL. libmpv plays them as one timeline via ``audio-files`` and
  keeps them in sync itself, so there is no ffmpeg remux stage delaying start.
  ffpyplayer takes a single input and could not do this.
* **Per-playback ALSA device.** ``audio-device=alsa/hw:X,Y`` is set per player
  instance, which is what the VideoEvent's audio_device option needs.
  ffpyplayer plays through SDL, whose device is fixed process-wide.
* Hardware H.264 decode, HLS/live input and seeking all come for free.

PiHome's SDL2 is built ``--enable-video-kmsdrm --disable-video-x11``
(``setup/install.sh``), so Kivy is DRM master on the bare console and a
*separate* mpv process could never draw to the screen. Decoding therefore has
to happen in-process, with mpv rendering into memory we own and blitting the
result to a Kivy texture -- the same shape as BambuLab's ``_update_texture()``.
"""

import ctypes
import os
import sys

from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

try:
    import numpy as _np
except Exception:  # pragma: no cover - numpy is a core requirement
    _np = None

try:
    import mpv as _mpv
    _IMPORT_ERROR = None
except Exception as e:  # ImportError, or OSError when libmpv1 is absent
    _mpv = None
    _IMPORT_ERROR = e


# ── python-mpv render-param compatibility ────────────────────────────────────
# python-mpv (through 1.0.8) only maps render params up to id 16 and omits the
# four software-render params entirely, so MpvRenderContext cannot be driven in
# 'sw' mode out of the box. The ids and types below are from libmpv's render.h
# and are stable API. Assigned rather than setdefault'ed so the calling
# convention below always matches these definitions even if a future
# python-mpv adds its own entries with a different shape.
if _mpv is not None:

    class _SwSize(ctypes.Structure):
        _fields_ = [("w", ctypes.c_int), ("h", ctypes.c_int)]

    class _SwStride(ctypes.Structure):
        _fields_ = [("stride", ctypes.c_size_t)]

    _mpv.MpvRenderParam.TYPES.update({
        "sw_size":    (17, _SwSize),
        "sw_format":  (18, str),
        "sw_stride":  (19, _SwStride),
        "sw_pointer": (20, ctypes.c_void_p),
    })


AVAILABLE = _mpv is not None


def check_playable():
    """Return (ok, reason). Reason is None when playback can run here.

    Guards macOS explicitly: Homebrew's libmpv crashes inside AppKit/ImageIO
    during mpv_create() when it is loaded outside an app bundle, and because
    that is a SIGSEGV rather than an exception it takes the whole PiHome
    process with it. The Pi (no AppKit) is unaffected. Set
    [video] allow_macos = 1 in base.ini to override if libmpv is ever fixed.
    """
    if _mpv is None:
        text = str(_IMPORT_ERROR or "")
        if "library" in text.lower() or "not found" in text.lower():
            return False, "libmpv not installed"
        if isinstance(_IMPORT_ERROR, ImportError):
            return False, "python-mpv not installed"
        return False, "Player unavailable"
    if sys.platform == "darwin":
        allow = CONFIG.get("video", "allow_macos", "0").strip().lower() in ("1", "true")
        if not allow:
            return False, "Video playback is Linux-only (libmpv crashes on macOS)"
    if _np is None:
        return False, "numpy not installed"
    return True, None


def unavailable_reason():
    """Human-readable reason playback can't run, or None when it can."""
    ok, reason = check_playable()
    return None if ok else reason


def probe_hardware_decode():
    """Best-effort check that H.264 hardware decode is wired up on this Pi.

    A Pi 3B decodes H.264 in hardware and nothing else; if the V4L2 codec nodes
    are missing (no ``vc4-kms-v3d`` overlay, or too small a ``gpu_mem`` split)
    mpv silently falls back to software and the only symptom is unexplained
    stutter. Returns (ok, message) -- advisory only, never blocks playback.
    """
    if not os.path.exists("/proc/device-tree/model"):
        return True, "not a Raspberry Pi, skipping hwdec probe"
    try:
        with open("/proc/device-tree/model", "rb") as f:
            model = f.read().decode("utf-8", "replace").strip("\x00").strip()
    except Exception:
        model = "unknown"
    nodes = [n for n in ("/dev/video10", "/dev/video11", "/dev/video12") if os.path.exists(n)]
    if not nodes:
        return False, (
            "{}: no V4L2 codec nodes (/dev/video10-12). Hardware H.264 decode is "
            "unavailable - check dtoverlay=vc4-kms-v3d and gpu_mem in /boot/config.txt. "
            "Playback will fall back to software and may stutter.".format(model)
        )
    return True, "{}: V4L2 codec nodes present ({})".format(model, ", ".join(nodes))


def normalize_audio_device(device):
    """Turn an ALSA device string into an mpv audio-device name.

    Accepts what ``aplay -l`` yields ("hw:0,0"), what mpv itself uses
    ("alsa/hw:0,0"), and empty/auto.
    """
    dev = (device or "").strip()
    if not dev or dev.lower() == "auto":
        return "auto"
    if "/" in dev:
        return dev
    return "alsa/{}".format(dev)


class VideoPlayer:
    """One playback session, rendering into a fixed-size RGBA buffer.

    ``render_frame()`` is driven from the Kivy clock on the main thread. The
    software renderer is single-threaded CPU work, but at 800x480 it is only a
    few milliseconds and this screen has no other drawing to do, so keeping it
    on the main thread avoids double-buffering and cross-thread texture rules.
    """

    def __init__(self, width, height, on_end=None, on_error=None):
        self.width = int(width)
        self.height = int(height)
        self._on_end = on_end
        self._on_error = on_error
        self._mpv = None
        self._ctx = None
        self._buf = None
        self._view = None
        self._alpha = None
        self._logged_hwdec = False
        self._stopping = False

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self, resolution, audio_device=None, hwdec="auto-safe",
              cache_secs=20, volume=100, loop=False):
        """Begin playing a resolver.Resolution. Raises RuntimeError if unusable."""
        ok, reason = check_playable()
        if not ok:
            raise RuntimeError(reason)

        self._stopping = False
        self._alloc_buffer()

        opts = dict(
            vo="libmpv",
            hwdec=hwdec or "auto-safe",
            audio_device=normalize_audio_device(audio_device),
            # We resolve URLs ourselves, so mpv must not spawn its own yt-dlp.
            ytdl=False,
            # 1GB of RAM on a Pi 3B: keep the demuxer buffer modest. Live HLS
            # still needs a real cache to ride out network jitter.
            cache="yes",
            cache_secs=max(2, int(cache_secs)),
            demuxer_max_bytes="24MiB",
            demuxer_max_back_bytes="8MiB",
            # Skip rather than stall when a frame arrives late.
            framedrop="vo",
            # Nothing composites over the video, so keep the CPU renderer lean.
            sw_fast=True,
            osc=False,
            osd_level=0,
            input_default_bindings=False,
            input_vo_keyboard=False,
            terminal=False,
        )
        if loop:
            opts["loop_file"] = "inf"

        try:
            # loglevel gates mpv_request_log_messages; without it python-mpv
            # defaults to 'terminal-default' and floods PIHOME_LOGGER.
            self._mpv = _mpv.MPV(log_handler=self._log, loglevel="error", **opts)
        except Exception as e:
            raise RuntimeError("Could not start player: {}".format(e))

        try:
            self._ctx = _mpv.MpvRenderContext(self._mpv, "sw")
        except Exception as e:
            self.stop()
            raise RuntimeError("Could not create render context: {}".format(e))

        try:
            self._mpv.volume = max(0, min(100, int(volume)))
        except Exception:
            pass

        @self._mpv.event_callback("end-file")
        def _ended(event):  # fires on python-mpv's event thread
            if self._stopping:
                return
            reason = ""
            try:
                reason = str(getattr(event.data, "reason", "") or "")
            except Exception:
                pass
            if "error" in reason.lower():
                self._fire(self._on_error, "Playback failed")
            else:
                self._fire(self._on_end, reason)

        # Separate audio track must be attached before play() so mpv opens both
        # as one timeline; setting it afterwards restarts the audio chain.
        if resolution.audio_url:
            self._mpv["audio-files"] = [resolution.audio_url]
        self._mpv.play(resolution.video_url)

    def stop(self):
        """Tear down the render context and player. Safe to call repeatedly."""
        self._stopping = True
        ctx, self._ctx = self._ctx, None
        if ctx is not None:
            try:
                ctx.free()
            except Exception:
                pass
        player, self._mpv = self._mpv, None
        if player is not None:
            try:
                player.terminate()
            except Exception:
                pass
        self._buf = None
        self._view = None
        self._alpha = None
        self._logged_hwdec = False

    # ── Rendering ────────────────────────────────────────────────────────────

    def _alloc_buffer(self):
        size = self.width * self.height * 4
        # render.h asks for 64-byte alignment on both pointer and stride for the
        # SIMD paths; over-allocate and offset rather than accept the slow path.
        raw = (ctypes.c_char * (size + 64))()
        addr = ctypes.addressof(raw)
        offset = (-addr) % 64
        self._buf = raw
        self._ptr = ctypes.c_void_p(addr + offset)
        arr = _np.frombuffer(raw, dtype=_np.uint8, count=size, offset=offset)
        self._view = arr.reshape(self.height, self.width, 4)
        self._alpha = self._view[:, :, 3]

    def render_frame(self):
        """Render one frame if mpv has a new one. Returns a buffer or None.

        The returned memoryview is only valid until the next call.
        """
        ctx = self._ctx
        if ctx is None:
            return None
        try:
            if not ctx.update():
                return None
            ctx.render(
                sw_size={"w": self.width, "h": self.height},
                sw_format="rgb0",
                sw_stride={"stride": self.width * 4},
                sw_pointer=self._ptr,
            )
        except Exception as e:
            PIHOME_LOGGER.error("VideoScreen: render failed: {}".format(e))
            return None

        # "rgb0" leaves the fourth byte as uninitialised garbage (render.h), so
        # it must be forced opaque or the texture blits transparent/flickering.
        self._alpha[:] = 255

        if not self._logged_hwdec:
            self._logged_hwdec = True
            self._log_hwdec()
        return memoryview(self._view.reshape(-1))

    def _log_hwdec(self):
        """Report whether hardware decode actually engaged, once per playback."""
        try:
            current = self._mpv.hwdec_current
        except Exception:
            return
        current = str(current or "no")
        if current in ("no", "none", ""):
            PIHOME_LOGGER.warn(
                "VideoScreen: hardware decode NOT active (hwdec-current=no) - "
                "decoding in software, expect stutter on a Pi 3B"
            )
        else:
            PIHOME_LOGGER.info("VideoScreen: hardware decode active ({})".format(current))

    # ── Transport ────────────────────────────────────────────────────────────

    def toggle_pause(self):
        if self._mpv is None:
            return False
        try:
            self._mpv.pause = not self._mpv.pause
            return bool(self._mpv.pause)
        except Exception:
            return False

    def seek(self, seconds):
        if self._mpv is None:
            return
        try:
            self._mpv.seek(seconds, reference="relative")
        except Exception:
            pass

    def nudge_volume(self, delta):
        if self._mpv is None:
            return None
        try:
            vol = max(0, min(100, int(self._mpv.volume or 0) + delta))
            self._mpv.volume = vol
            return vol
        except Exception:
            return None

    @property
    def position(self):
        try:
            return float(self._mpv.time_pos or 0.0)
        except Exception:
            return 0.0

    @property
    def duration(self):
        try:
            return float(self._mpv.duration or 0.0)
        except Exception:
            return 0.0

    @property
    def paused(self):
        try:
            return bool(self._mpv.pause)
        except Exception:
            return False

    # ── Internals ────────────────────────────────────────────────────────────

    def _fire(self, cb, arg):
        if cb is None:
            return
        try:
            cb(arg)
        except Exception as e:
            PIHOME_LOGGER.error("VideoScreen: callback error: {}".format(e))

    def _log(self, level, prefix, text):
        message = "{}: {}".format(prefix, (text or "").strip())
        if level in ("fatal", "error"):
            PIHOME_LOGGER.error("VideoScreen/mpv {}".format(message))
        elif level == "warn":
            PIHOME_LOGGER.warn("VideoScreen/mpv {}".format(message))
