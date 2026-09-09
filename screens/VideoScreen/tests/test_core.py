"""Headless tests for the VideoScreen source/format logic.

No Kivy, no libmpv, no GL context, no network:

    venv/bin/python screens/VideoScreen/tests/test_core.py
"""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from screens.VideoScreen.resolver import (  # noqa: E402
    DIRECT,
    EXTRACT,
    LOCAL,
    Resolution,
    _friendly_error,
    build_command,
    classify,
    format_selector,
    parse_output,
    resolve,
)
from screens.VideoScreen.player import normalize_audio_device  # noqa: E402


class TestClassify(unittest.TestCase):
    def test_youtube_needs_extraction(self):
        self.assertEqual(classify("https://www.youtube.com/watch?v=aqz-KE-bpKQ"), EXTRACT)
        self.assertEqual(classify("https://youtu.be/aqz-KE-bpKQ"), EXTRACT)
        self.assertEqual(classify("https://vimeo.com/12345"), EXTRACT)

    def test_direct_media_urls_skip_ytdlp(self):
        for url in (
            "https://example.com/clip.mp4",
            "http://example.com/a/b/stream.m3u8",
            "https://example.com/movie.MKV",
            "rtsp://cam.local/stream",
            "rtsps://bblp:code@printer:322/streaming/live/1",
        ):
            self.assertEqual(classify(url), DIRECT, url)

    def test_query_string_does_not_defeat_extension_match(self):
        self.assertEqual(classify("https://cdn.example.com/v.mp4?token=abc&x=1"), DIRECT)
        self.assertEqual(classify("https://cdn.example.com/v.m3u8#frag"), DIRECT)

    def test_local_paths(self):
        self.assertEqual(classify("/home/pi/clip.mp4"), LOCAL)
        self.assertEqual(classify("uploads/video.mkv"), LOCAL)

    def test_empty_source(self):
        self.assertEqual(classify(""), EXTRACT)
        self.assertEqual(classify(None), EXTRACT)


class TestFormatSelector(unittest.TestCase):
    def test_prefers_hardware_decodable_avc1(self):
        sel = format_selector(480)
        self.assertTrue(sel.startswith("bv*[vcodec^=avc1][height<=480][fps<=31]+ba[ext=m4a]"))

    def test_every_rung_is_present_and_ordered(self):
        sel = format_selector(480)
        rungs = sel.split("/")
        self.assertEqual(len(rungs), 6)
        self.assertEqual(rungs[-1], "b")

    def test_respects_custom_cap(self):
        self.assertIn("height<=720", format_selector(720))
        self.assertNotIn("height<=480", format_selector(720))

    def test_bad_input_falls_back_to_panel_height(self):
        for bad in (None, "", "abc", object()):
            self.assertIn("height<=480", format_selector(bad))

    def test_absurdly_small_cap_is_clamped(self):
        self.assertIn("height<=144", format_selector(1))


class TestBuildCommand(unittest.TestCase):
    def test_is_argv_list_never_a_shell_string(self):
        cmd = build_command("https://youtu.be/x")
        self.assertIsInstance(cmd, list)
        self.assertTrue(all(isinstance(part, str) for part in cmd))

    def test_url_is_terminated_so_it_cannot_be_read_as_options(self):
        # The URL arrives from MQTT/HTTP and PiHome runs as root, so a source
        # starting with "-" must never be parsed as a yt-dlp flag.
        cmd = build_command("--exec=rm -rf /")
        self.assertEqual(cmd[-2], "--")
        self.assertEqual(cmd[-1], "--exec=rm -rf /")

    def test_cookies_included_only_when_given(self):
        self.assertNotIn("--cookies", build_command("u"))
        self.assertIn("--cookies", build_command("u", cookies="/tmp/c.txt"))


class TestParseOutput(unittest.TestCase):
    SPLIT = (
        "TITLE:Big Buck Bunny\n"
        "LIVE:False\n"
        "DUR:635\n"
        "https://cdn.example.com/video?itag=135\n"
        "https://cdn.example.com/audio?itag=140\n"
    )

    def test_split_streams(self):
        r = parse_output(self.SPLIT)
        self.assertTrue(r.is_split)
        self.assertEqual(r.video_url, "https://cdn.example.com/video?itag=135")
        self.assertEqual(r.audio_url, "https://cdn.example.com/audio?itag=140")
        self.assertEqual(r.title, "Big Buck Bunny")
        self.assertFalse(r.is_live)
        self.assertEqual(r.duration, 635.0)

    def test_single_muxed_stream_has_no_audio_url(self):
        r = parse_output("TITLE:Clip\nLIVE:False\nDUR:10\nhttps://example.com/one.mp4\n")
        self.assertFalse(r.is_split)
        self.assertIsNone(r.audio_url)

    def test_live_stream(self):
        r = parse_output("TITLE:Radio\nLIVE:True\nDUR:None\nhttps://x/hls.m3u8\n")
        self.assertTrue(r.is_live)
        self.assertEqual(r.duration, 0.0)   # 'None' duration must not raise

    def test_metadata_order_does_not_matter(self):
        r = parse_output("https://x/v.mp4\nDUR:5\nTITLE:After\nLIVE:False\n")
        self.assertEqual(r.title, "After")
        self.assertEqual(r.video_url, "https://x/v.mp4")

    def test_title_containing_a_url_is_not_mistaken_for_a_stream(self):
        r = parse_output("TITLE:https://spam.example.com watch now\nhttps://x/v.mp4\n")
        self.assertFalse(r.is_split)
        self.assertEqual(r.video_url, "https://x/v.mp4")

    def test_no_urls_returns_none(self):
        self.assertIsNone(parse_output("TITLE:Nothing\nLIVE:False\n"))
        self.assertIsNone(parse_output(""))
        self.assertIsNone(parse_output(None))


class TestFriendlyError(unittest.TestCase):
    def test_known_cases(self):
        self.assertEqual(_friendly_error("ERROR: Private video. Sign in"), "Video is private")
        self.assertEqual(_friendly_error("ERROR: Video unavailable"), "Video unavailable")
        self.assertEqual(_friendly_error("ERROR: Unsupported URL: x"), "Unsupported link")
        self.assertEqual(_friendly_error(""), "Could not load video")

    def test_unknown_error_is_stripped_and_truncated(self):
        out = _friendly_error("ERROR: " + "x" * 400)
        self.assertFalse(out.startswith("ERROR:"))
        self.assertLessEqual(len(out), 120)


class TestResolveWithoutNetwork(unittest.TestCase):
    def test_missing_local_file_raises(self):
        with self.assertRaises(RuntimeError):
            resolve("/definitely/not/here.mp4")

    def test_existing_local_file_skips_ytdlp(self):
        # Uses this test file itself; resolve() must not shell out at all.
        r = resolve(__file__)
        self.assertEqual(r.video_url, __file__)
        self.assertIsNone(r.audio_url)
        self.assertFalse(r.is_live)

    def test_direct_manifest_is_marked_live(self):
        r = resolve("https://example.com/live/stream.m3u8")
        self.assertTrue(r.is_live)
        self.assertIsNone(r.audio_url)


class TestAudioDevice(unittest.TestCase):
    def test_aplay_style_device_gets_alsa_prefix(self):
        self.assertEqual(normalize_audio_device("hw:0,0"), "alsa/hw:0,0")
        self.assertEqual(normalize_audio_device(" hw:1,0 "), "alsa/hw:1,0")

    def test_already_qualified_device_is_untouched(self):
        self.assertEqual(normalize_audio_device("alsa/hw:2,0"), "alsa/hw:2,0")
        self.assertEqual(normalize_audio_device("pulse/some.sink"), "pulse/some.sink")

    def test_blank_and_auto(self):
        for value in ("", None, "auto", "  "):
            self.assertEqual(normalize_audio_device(value), "auto")


class TestResolutionModel(unittest.TestCase):
    def test_is_split(self):
        self.assertTrue(Resolution("v", "a").is_split)
        self.assertFalse(Resolution("v").is_split)
        self.assertFalse(Resolution("v", "").is_split)


if __name__ == "__main__":
    unittest.main(verbosity=2)
