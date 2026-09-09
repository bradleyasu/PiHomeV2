# VideoScreen

Full-screen video playback driven entirely by events. Hidden from the app menu.

## How it works

1. A `video` event arrives (MQTT / HTTP / WebSocket) and the screen becomes current.
2. `resolver.py` classifies the source. Local files and direct media URLs
   (`.mp4`, `.m3u8`, `rtsp://`, ...) go straight to the player. Everything else
   is resolved with `yt-dlp -g`, which returns a separate H.264 video URL and an
   AAC audio URL.
3. `player.py` hands both to libmpv at once (`audio-files`), which plays them as
   one synchronised timeline. **There is no mux or transcode step**, so playback
   starts as soon as the URLs resolve (~2-3s for YouTube, instant for direct URLs).

## Why libmpv and not ffpyplayer

PiHome's SDL2 is built `--enable-video-kmsdrm --disable-video-x11`
(`setup/install.sh`), so Kivy is DRM master on the bare console and a *separate*
mpv/ffplay process could never draw to the screen. Decoding has to be in-process.

ffpyplayer (which BambuLab uses for its camera) can render frames, but it takes a
single input and plays audio through SDL, so it can offer neither the two-URL
sync nor a per-playback ALSA device. libmpv does both. Rendering still follows
BambuLab's pattern: decode off the UI path, blit into a `Texture`, bind it to a
KV `Rectangle`.

`ffplay` was ruled out entirely -- it accepts only one input.

## Quality on a Raspberry Pi 3B

The 3B decodes **H.264 in hardware and nothing else**. VP9 and AV1 (what YouTube
serves by default) fall back to software and stutter badly, so every format
selector pins `vcodec^=avc1` and caps frame rate at 30.

`max_height` defaults to **480** because the panel is 800x480 -- a 480p stream is
854 px wide, already wider than the display. Raising the cap costs decode budget
without adding a visible pixel.

## Live streams

Live works, but the format shape is completely different from a VOD and the
selector has to account for it. `yt-dlp -F` on a YouTube live stream returns:

```
233 mp4 audio only  m3u8 | audio only          Default, low
234 mp4 audio only  m3u8 | audio only          Default, high
231 mp4 854x480  30 m3u8 | avc1.4D401F  video only
232 mp4 1280x720 30 m3u8 | avc1.4D401F  video only
```

Two things follow, and both broke the first implementation:

1. **There are no muxed formats at all.** Every format is video-only or
   audio-only, so a bare `b` (best *combined*) rung can never match a live
   stream, however far down the ladder it sits.
2. **Live audio is `ext=mp4`, never `m4a`.** Any rung ending `+ba[ext=m4a]`
   fails, so the selector needs a bare `+ba` rung high up.

Together those produced `Requested format is not available`, which -- because
it contains the substring "not available" -- was then reported to the user as
the thoroughly misleading **"Video unavailable"**.

Live streams are otherwise handled like any other split-stream source: mpv
plays the two HLS playlists as one timeline via `audio-files`, verified in
sync at `avsync +0`. `duration` is 0 for live, which is what hides the
progress bar.

Note that YouTube rotates the video ID of a 24/7 stream, so a saved
`watch?v=...` link eventually resolves to an ended broadcast
("This live stream recording is not available"). Prefer the channel form:

```
https://www.youtube.com/@lofigirl/live
```

## Settings

This screen is hidden, and `screens/Settings/settings.py` skips hidden manifests,
so there is no Settings panel. Edit the `[video]` section of `base.ini`:

| Key | Default | Meaning |
|-----|---------|---------|
| `max_height` | `480` | Max video height in pixels |
| `audio_device` | `auto` | Default ALSA device, e.g. `hw:0,0` |
| `hwdec` | `auto-safe` | mpv hardware decode mode |
| `cache_secs` | `20` | Demuxer cache; raise for flaky networks / live |
| `ytdlp_path` | `yt-dlp` | Path to the yt-dlp binary |
| `resolve_timeout` | `45` | Seconds to wait for yt-dlp |
| `volume` | `100` | Starting volume (0-100) |
| `cookies_file` | | Cookie jar for age/login-gated videos |
| `allow_macos` | `0` | Override the macOS safety guard (see below) |

Every one of these can be overridden per event.

## Events

| Type | Fields |
|------|--------|
| `video` | `url` (required), `audio_device`, `quality`, `timeout`, `loop` |
| `video_stop` | -- |
| `video_update_ytdlp` | -- |

```json
{ "type": "video", "url": "https://youtu.be/aqz-KE-bpKQ", "audio_device": "hw:0,0" }
```

`audio_device` is offered as a dropdown in the web UI, populated from `aplay -l`
via the same helper the `aplay` event uses.

`video_update_ytdlp` exists because YouTube changes break extraction every few
weeks; without it, fixing playback on a kiosk means finding a keyboard.

## Controls

| Input | Action |
|-------|--------|
| Tap | Pause / resume |
| Rotary turn | Volume |
| Rotary turn (held) | Seek +/- 10s |
| Rotary press | Pause / resume |
| Rotary long press | Stop and go back |

Tapping deliberately does *not* exit (unlike `DisplayImageEvent`) so an accidental
brush cannot kill a video. The hamburger menu still leaves the screen.

## Dependencies

`yt-dlp` and `python-mpv` are declared in the manifest and auto-install at
startup, **but a restart is required** before they can be used. `libmpv1` is a
system package already installed by `setup/install.sh`.

## macOS

Homebrew's libmpv crashes inside AppKit/ImageIO during `mpv_create()` when loaded
outside an app bundle, and as a SIGSEGV it would take the whole PiHome process
down. Playback is therefore refused on macOS with a message; set
`[video] allow_macos = 1` to override. The Pi has no AppKit and is unaffected.

## Tests

```
venv/bin/python screens/VideoScreen/tests/test_core.py
```

Covers source classification, the format-selector ladder, argv construction
(including that a `-`-prefixed URL can't be read as a yt-dlp flag), yt-dlp output
parsing and ALSA device normalisation. No Kivy, libmpv, GL or network.
