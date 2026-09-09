"""Source classification and yt-dlp format selection for the VideoScreen.

Deliberately free of Kivy and libmpv imports so the whole module can be
exercised headlessly (see tests/test_resolver.py), matching the pure-logic
split used by ``bambustate.py`` and ``calstore.py``.

The Raspberry Pi 3B decodes H.264 in hardware and nothing else -- VP9, AV1 and
HEVC all fall back to software and turn into a slideshow. Every selector built
here therefore pins ``vcodec`` to ``avc1`` and caps the frame rate, and the
height ceiling defaults to the 800x480 panel rather than to "best available".
A 480p stream is already slightly wider than the panel, so raising the cap
costs decode budget without adding a single visible pixel.
"""

import os
import re
import subprocess

from util.phlog import PIHOME_LOGGER

# Containers/schemes mpv opens directly. Routing these through yt-dlp would add
# seconds of extractor work to a URL that is already a playable stream.
_DIRECT_EXT = (
    ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".ts", ".flv",
    ".m3u8", ".mpd", ".mp3", ".m4a", ".flac", ".wav", ".ogg", ".opus",
)
_DIRECT_SCHEMES = ("rtsp://", "rtsps://", "rtmp://", "rtmps://", "udp://", "srt://", "file://")
_URL_SCHEMES = ("http://", "https://") + _DIRECT_SCHEMES

LOCAL = "local"
DIRECT = "direct"
EXTRACT = "extract"

# Only 30fps-class content is realistic on a Pi 3B. 31 rather than 30 so that
# 30000/1001 (29.97) and a stream that rounds to 30 both pass the filter.
_FPS_CAP = 31
# Height the ladder relaxes to when nothing exists at the configured cap.
_RELAX_HEIGHT = 720


class Resolution:
    """The outcome of resolving a source into something mpv can play.

    ``audio_url`` is None whenever the source is already muxed (a progressive
    file, or an HLS variant for a live stream), in which case mpv is handed a
    single input and no ``--audio-file`` is needed.
    """

    def __init__(self, video_url, audio_url=None, title="", is_live=False, duration=0.0):
        self.video_url = video_url
        self.audio_url = audio_url
        self.title = title
        self.is_live = is_live
        self.duration = duration

    @property
    def is_split(self):
        return bool(self.audio_url)

    def __repr__(self):
        return "<Resolution split={} live={} title={!r}>".format(
            self.is_split, self.is_live, self.title
        )


# Character ranges no bundled PiHome font can draw. Neither Nunito nor
# arial-unicode-ms contains emoji, and YouTube titles are full of them -- an
# uncovered codepoint renders as a tofu box (CLAUDE.md gotcha #5). Accents,
# CJK and typographic punctuation ARE covered by ArialUnicode, so only the
# symbol/emoji ranges and the private-use area (which would collide with
# MaterialIcons glyphs) are stripped.
_UNDRAWABLE = (
    (0x2190, 0x21FF),    # arrows
    (0x2600, 0x27BF),    # misc symbols and dingbats
    (0x2B00, 0x2BFF),    # misc symbols and arrows
    (0xE000, 0xF8FF),    # private use (MaterialIcons lives here)
    (0xFE00, 0xFE0F),    # variation selectors
    (0x1F000, 0x1FAFF),  # emoji and pictographs
)


def sanitize_title(text):
    """Strip characters no bundled font can render, and collapse whitespace.

    Titles come from arbitrary uploads, so they reach the Label as-is; without
    this a title like "lofi hip hop radio [emoji] beats" paints a tofu box on
    the panel.
    """
    if not text:
        return ""
    kept = []
    for ch in text:
        cp = ord(ch)
        if cp == 0x200D or cp > 0x1FFFF:          # ZWJ, and anything exotic
            continue
        if any(lo <= cp <= hi for lo, hi in _UNDRAWABLE):
            continue
        kept.append(ch)
    return re.sub(r"\s+", " ", "".join(kept)).strip()

def classify(source):
    """Return LOCAL, DIRECT or EXTRACT for *source*.

    LOCAL and DIRECT both bypass yt-dlp entirely and start effectively
    instantly; EXTRACT is the only path that pays extractor cost.
    """
    if not source:
        return EXTRACT
    src = source.strip()
    lowered = src.lower()

    if lowered.startswith(_DIRECT_SCHEMES):
        return DIRECT
    if not lowered.startswith(_URL_SCHEMES):
        # Anything that isn't a URL is treated as a path on the Pi.
        return LOCAL
    # An http(s) URL whose path ends in a media extension is a plain stream.
    path = lowered.split("?", 1)[0].split("#", 1)[0]
    if path.endswith(_DIRECT_EXT):
        return DIRECT
    return EXTRACT


def format_selector(max_height=480):
    """Build a layered yt-dlp format selector, most-preferred first.

    Each rung relaxes exactly one constraint so that an unusual upload degrades
    instead of failing outright. avc1 is preferred the whole way down because a
    soft 480p H.264 stream plays and a crisp VP9 one does not.
    """
    try:
        cap = max(144, int(max_height))
    except (TypeError, ValueError):
        cap = 480
    relax = max(cap, _RELAX_HEIGHT)
    return "/".join([
        # Ideal: hardware-decodable video at panel height, separate AAC audio.
        "bv*[vcodec^=avc1][height<=%d][fps<=%d]+ba[ext=m4a]" % (cap, _FPS_CAP),
        # Same, but any audio container. Required for live: YouTube serves
        # live audio as audio-only HLS with ext=mp4, never m4a, so an
        # m4a-only rung can never match a live stream.
        "bv*[vcodec^=avc1][height<=%d][fps<=%d]+ba" % (cap, _FPS_CAP),
        # Same height, allow 50/60fps rather than dropping resolution.
        "bv*[vcodec^=avc1][height<=%d]+ba" % cap,
        # Nothing at the cap: allow a taller avc1 stream, mpv will downscale.
        "bv*[vcodec^=avc1][height<=%d][fps<=%d]+ba" % (relax, _FPS_CAP),
        # Progressive (already muxed) H.264 -- still preferred over a split
        # non-avc1 pair, because only H.264 decodes in hardware on a Pi 3B.
        "b[vcodec^=avc1][height<=%d]" % relax,
        # Last resorts, any codec. The split form has to come before the muxed
        # one: a live stream offers NO muxed formats at all, so a bare "b"
        # cannot match one however far down the ladder it sits.
        "bv*[height<=%d]+ba" % relax,
        "b[height<=%d]" % relax,
        "b",
    ])


def build_command(source, max_height=480, ytdlp="yt-dlp", cookies=None):
    """Return the argv list for resolving *source*.

    Always an argv list -- never a shell string. The URL arrives from MQTT,
    HTTP or WebSocket and PiHome runs as root (``sudo -E python3 main.py``), so
    handing it to a shell would be a command-injection hole.
    """
    cmd = [
        ytdlp,
        "-q", "--no-warnings", "--no-playlist", "--no-progress",
        "-f", format_selector(max_height),
        "--print", "TITLE:%(title)s",
        "--print", "LIVE:%(is_live)s",
        "--print", "DUR:%(duration)s",
        "-g",
    ]
    if cookies:
        cmd += ["--cookies", cookies]
    cmd += ["--", source]
    return cmd


def parse_output(stdout):
    """Parse the combined --print/-g output into a Resolution.

    Keys off line prefixes rather than line position, so the parser survives
    yt-dlp reordering its metadata and URL output.
    """
    title, is_live, duration = "", False, 0.0
    urls = []
    for raw in (stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("TITLE:"):
            title = line[6:].strip()
        elif line.startswith("LIVE:"):
            is_live = line[5:].strip().lower() == "true"
        elif line.startswith("DUR:"):
            try:
                duration = float(line[4:].strip())
            except ValueError:
                duration = 0.0
        elif line.lower().startswith(_URL_SCHEMES):
            urls.append(line)

    if not urls:
        return None
    # yt-dlp emits the video URL first, then audio, for a "video+audio" match.
    video = urls[0]
    audio = urls[1] if len(urls) > 1 else None
    return Resolution(video, audio, title=sanitize_title(title),
                      is_live=is_live, duration=duration)


def resolve(source, max_height=480, ytdlp="yt-dlp", timeout=45, cookies=None):
    """Resolve *source* into a Resolution, or raise RuntimeError.

    Blocking and network-bound -- always call from a worker thread.
    """
    kind = classify(source)
    if kind in (LOCAL, DIRECT):
        title = os.path.basename(source.split("?", 1)[0]) or source
        # An HLS/DASH manifest handed over directly is very likely a live feed;
        # treating it as such only affects whether a seek bar would make sense.
        live = source.lower().split("?", 1)[0].endswith((".m3u8", ".mpd"))
        if kind == LOCAL and not os.path.exists(source):
            raise RuntimeError("File not found: {}".format(source))
        return Resolution(source, None, title=sanitize_title(title), is_live=live)

    cmd = build_command(source, max_height=max_height, ytdlp=ytdlp, cookies=cookies)
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout
        )
    except FileNotFoundError:
        raise RuntimeError("yt-dlp not installed")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Timed out resolving video")

    stdout = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        PIHOME_LOGGER.error("VideoScreen: yt-dlp failed: {}".format(stderr[:500]))
        raise RuntimeError(_friendly_error(stderr))

    result = parse_output(stdout)
    if result is None:
        raise RuntimeError("No playable stream found")
    return result


def _friendly_error(stderr):
    """Condense a yt-dlp stderr dump into something readable on an 800x480 panel."""
    text = re.sub(r"\s+", " ", (stderr or "")).strip()
    if not text:
        return "Could not load video"
    lowered = text.lower()
    # Specific causes first: several of these also contain the generic
    # "not available", which previously swallowed them and reported a healthy
    # live stream as "Video unavailable".
    if "requested format is not available" in lowered:
        return "No compatible video format"
    if "live stream recording is not available" in lowered:
        return "Live stream has ended"
    if "live event has ended" in lowered:
        return "Live stream has ended"
    if "live event will begin" in lowered or "premieres in" in lowered:
        return "Live stream has not started"
    if "not currently live" in lowered:
        return "Channel is not live"
    if "private video" in lowered:
        return "Video is private"
    if "video unavailable" in lowered or "not available" in lowered:
        return "Video unavailable"
    if "sign in" in lowered or ("age" in lowered and "confirm" in lowered):
        return "Video requires sign-in"
    if "unsupported url" in lowered:
        return "Unsupported link"
    if "network" in lowered or "resolve host" in lowered or "timed out" in lowered:
        return "Network error"
    # yt-dlp prefixes its own messages with "ERROR: "; strip it and truncate.
    text = re.sub(r"^ERROR:\s*", "", text, flags=re.I)
    return text[:120]


def update_ytdlp(ytdlp="yt-dlp", timeout=180):
    """Self-update yt-dlp. Returns (ok, message).

    YouTube changes break extraction every few weeks, so this is exposed as the
    ``video_update_ytdlp`` event rather than requiring shell access to the Pi.
    """
    try:
        proc = subprocess.run(
            [ytdlp, "-U"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout
        )
    except FileNotFoundError:
        return False, "yt-dlp not installed"
    except subprocess.TimeoutExpired:
        return False, "Update timed out"
    out = proc.stdout.decode("utf-8", "replace").strip()
    tail = out.splitlines()[-1] if out else ""
    return proc.returncode == 0, (tail or "Updated")[:160]
