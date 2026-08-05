"""Headless tests for the BluetoothConnect wire protocol.

No Kivy, no bleak, no hardware, no GL context:

    python3 screens/BluetoothConnect/tests/test_protocol.py
"""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from screens.BluetoothConnect.protocol import (  # noqa: E402
    DEFAULT_SERVICE_UUID,
    LineAssembler,
    chunk,
    normalize_uuid,
    parse_command,
    substitute,
)


class TestLineAssembler(unittest.TestCase):

    def test_whole_line_in_one_fragment(self):
        self.assertEqual(LineAssembler().feed(b"button_a\n"), ["button_a"])

    def test_line_split_across_fragments(self):
        asm = LineAssembler()
        self.assertEqual(asm.feed(b"butt"), [])
        self.assertEqual(asm.feed(b"on_"), [])
        self.assertEqual(asm.feed(b"a\n"), ["button_a"])

    def test_several_lines_in_one_fragment(self):
        self.assertEqual(
            LineAssembler().feed(b"a\nb\nc\n"), ["a", "b", "c"]
        )

    def test_trailing_partial_is_kept_for_next_fragment(self):
        asm = LineAssembler()
        self.assertEqual(asm.feed(b"a\npart"), ["a"])
        self.assertEqual(asm.pending, 4)
        self.assertEqual(asm.feed(b"ial\n"), ["partial"])
        self.assertEqual(asm.pending, 0)

    def test_crlf_and_whitespace_are_stripped(self):
        self.assertEqual(LineAssembler().feed(b"  button_a \r\n"), ["button_a"])

    def test_blank_lines_are_dropped(self):
        self.assertEqual(LineAssembler().feed(b"\n\n\nx\n"), ["x"])

    def test_overflow_clears_the_buffer(self):
        asm = LineAssembler(max_line=16)
        self.assertEqual(asm.feed(b"x" * 40), [])
        self.assertEqual(asm.overflows, 1)
        self.assertEqual(asm.pending, 0)
        # Still usable afterwards.
        self.assertEqual(asm.feed(b"ok\n"), ["ok"])

    def test_flush_recovers_a_line_with_no_newline(self):
        asm = LineAssembler()
        self.assertEqual(asm.feed(b"no_newline"), [])
        self.assertEqual(asm.flush(), "no_newline")
        self.assertIsNone(asm.flush())

    def test_invalid_utf8_does_not_raise(self):
        self.assertEqual(len(LineAssembler().feed(b"\xff\xfe\n")), 1)


class TestParseCommand(unittest.TestCase):

    def test_bare_token(self):
        self.assertEqual(parse_command("button_a"), ("button_a", None))

    def test_colon_value(self):
        self.assertEqual(parse_command("dial:12"), ("dial", "12"))

    def test_equals_value(self):
        self.assertEqual(parse_command("dial=12"), ("dial", "12"))

    def test_case_and_whitespace_normalized(self):
        self.assertEqual(parse_command("  Button_A  "), ("button_a", None))
        self.assertEqual(parse_command("Dial : 12 "), ("dial", "12"))

    def test_value_may_contain_separators(self):
        self.assertEqual(parse_command("msg:a:b=c"), ("msg", "a:b=c"))

    def test_empty_value_is_none(self):
        self.assertEqual(parse_command("dial:"), ("dial", None))

    def test_empty_line(self):
        self.assertEqual(parse_command(""), ("", None))
        self.assertEqual(parse_command("   "), ("", None))

    def test_leading_separator_is_not_a_split(self):
        self.assertEqual(parse_command(":oops"), (":oops", None))


class TestSubstitute(unittest.TestCase):

    def test_replaces_in_nested_values(self):
        event = {"type": "toast", "message": "got $1", "nested": {"level": "$1"}}
        self.assertEqual(
            substitute(event, "42"),
            {"type": "toast", "message": "got 42", "nested": {"level": "42"}},
        )

    def test_replaces_inside_lists(self):
        event = {"type": "multi", "events": [{"type": "toast", "message": "$1"}]}
        self.assertEqual(substitute(event, "hi")["events"][0]["message"], "hi")

    def test_does_not_mutate_the_original(self):
        event = {"type": "toast", "message": "$1"}
        substitute(event, "x")
        self.assertEqual(event["message"], "$1")

    def test_none_value_leaves_placeholder_alone(self):
        event = {"type": "toast", "message": "$1"}
        self.assertEqual(substitute(event, None)["message"], "$1")

    def test_non_string_values_survive(self):
        event = {"type": "timer", "seconds": 30, "on": True, "off": None}
        self.assertEqual(substitute(event, "9"), event)


class TestNormalizeUuid(unittest.TestCase):

    def test_blank_falls_back(self):
        self.assertEqual(normalize_uuid("", DEFAULT_SERVICE_UUID), DEFAULT_SERVICE_UUID)
        self.assertEqual(normalize_uuid(None, DEFAULT_SERVICE_UUID), DEFAULT_SERVICE_UUID)

    def test_junk_falls_back(self):
        self.assertEqual(normalize_uuid("not-a-uuid", DEFAULT_SERVICE_UUID), DEFAULT_SERVICE_UUID)
        self.assertEqual(normalize_uuid("87e85cbe", DEFAULT_SERVICE_UUID), DEFAULT_SERVICE_UUID)

    def test_uppercase_and_braces_accepted(self):
        self.assertEqual(
            normalize_uuid("{87E85CBE-0094-417B-963B-AA888C375C36}", "fallback"),
            DEFAULT_SERVICE_UUID,
        )

    def test_valid_custom_uuid_passes_through(self):
        custom = "11112222-3333-4444-5555-666677778888"
        self.assertEqual(normalize_uuid(custom, DEFAULT_SERVICE_UUID), custom)


class TestChunk(unittest.TestCase):

    def test_adds_newline_and_fits_the_minimum_mtu(self):
        parts = chunk("led:on")
        self.assertEqual(b"".join(parts), b"led:on\n")
        self.assertTrue(all(len(p) <= 20 for p in parts))

    def test_long_text_is_split(self):
        parts = chunk("x" * 55)
        self.assertEqual(len(parts), 3)
        self.assertEqual(b"".join(parts), b"x" * 55 + b"\n")

    def test_existing_newline_not_doubled(self):
        self.assertEqual(b"".join(chunk("a\n")), b"a\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
