"""Headless tests for the LIFX LAN protocol layer.

No Kivy, no network, no bulb:

    python3 screens/LIFX/tests/test_protocol.py
"""

import os
import struct
import sys
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from screens.LIFX import protocol as p  # noqa: E402


class TestFraming(unittest.TestCase):

    def test_golden_get_service_frame(self):
        """Byte-exact GetService broadcast.

        This one assertion pins size=36, the 0x3400 protocol word, little-endian
        ordering and the whole header layout simultaneously.  If the wire format
        is ever wrong, it fails here first.
        """
        frame = p.pack(p.GET_SERVICE, source=0x12345678, sequence=0)
        expected = bytes.fromhex(
            "2400"              # size = 36
            "0034"              # protocol 1024 | addressable | tagged = 0x3400
            "78563412"          # source = 0x12345678, little-endian
            "0000000000000000"  # target = broadcast
            "000000000000"      # reserved
            "00"                # flags: no res_required, no ack_required
            "00"                # sequence
            "0000000000000000"  # reserved
            "0200"              # type = 2 (GetService)
            "0000"              # reserved
        )
        self.assertEqual(frame, expected)
        self.assertEqual(len(frame), p.HEADER_SIZE)

    def test_unicast_protocol_word(self):
        """Addressing a serial clears `tagged` but must keep `addressable` set."""
        frame = p.pack(p.LIGHT_GET, serial="d073d5123456", source=1, sequence=7)
        (proto,) = struct.unpack("<H", frame[2:4])
        self.assertEqual(proto, 0x1400)
        self.assertEqual(proto & 0x0FFF, p.PROTOCOL)
        self.assertTrue(proto & (1 << 12), "addressable must be set on unicast")
        self.assertFalse(proto & (1 << 13), "tagged must be clear on unicast")

    def test_frame_address_flag_bits(self):
        """res_required is bit 0, ack_required is bit 1 - reversing them breaks acks."""
        def flag_byte(**kw):
            return p.pack(p.LIGHT_GET, serial="d073d5123456", **kw)[22]

        self.assertEqual(flag_byte(), 0x00)
        self.assertEqual(flag_byte(res_required=True), 0x01)
        self.assertEqual(flag_byte(ack_required=True), 0x02)
        self.assertEqual(flag_byte(res_required=True, ack_required=True), 0x03)

    def test_round_trip_all_flag_combinations(self):
        payload = b"\x01\x02\x03\x04"
        for serial in (None, "d073d5123456"):
            for ack in (False, True):
                for res in (False, True):
                    frame = p.pack(p.LIGHT_STATE, payload, source=0xDEADBEEF,
                                   sequence=42, serial=serial,
                                   ack_required=ack, res_required=res)
                    out = p.unpack(frame)
                    self.assertEqual(out.msg_type, p.LIGHT_STATE)
                    self.assertEqual(out.source, 0xDEADBEEF)
                    self.assertEqual(out.sequence, 42)
                    self.assertEqual(out.serial, serial)
                    self.assertEqual(out.tagged, serial is None)
                    self.assertEqual(out.ack_required, ack)
                    self.assertEqual(out.res_required, res)
                    self.assertEqual(out.payload, payload)
                    self.assertEqual(out.size, p.HEADER_SIZE + len(payload))

    def test_sequence_wraps_into_one_byte(self):
        self.assertEqual(p.unpack(p.pack(p.LIGHT_GET, sequence=255)).sequence, 255)
        self.assertEqual(p.unpack(p.pack(p.LIGHT_GET, sequence=256)).sequence, 0)

    def test_short_frame_raises_protocol_error(self):
        with self.assertRaises(p.ProtocolError):
            p.unpack(b"\x00" * 10)

    def test_foreign_protocol_raises(self):
        frame = bytearray(p.pack(p.GET_SERVICE))
        frame[2:4] = struct.pack("<H", 999)
        with self.assertRaises(p.ProtocolError):
            p.unpack(bytes(frame))

    def test_truncated_datagram_does_not_over_read(self):
        """A UDP read shorter than the declared size yields what actually arrived."""
        frame = p.pack(p.LIGHT_STATE, b"\xAA" * 52, serial="d073d5123456")
        out = p.unpack(frame[:-10])
        self.assertEqual(len(out.payload), 42)


class TestSerials(unittest.TestCase):

    def test_target_is_mac_in_order_plus_two_zero_bytes(self):
        self.assertEqual(p.serial_to_target("d073d5123456"),
                         bytes.fromhex("d073d5123456") + b"\x00\x00")

    def test_round_trip_including_leading_zero_serial(self):
        for serial in ("d073d5123456", "00073d512345", "000000000001"):
            self.assertEqual(p.target_to_serial(p.serial_to_target(serial)), serial)

    def test_all_zero_target_is_broadcast(self):
        self.assertIsNone(p.target_to_serial(b"\x00" * 8))

    def test_normalize_accepts_common_separator_styles(self):
        for text in ("d0:73:d5:12:34:56", "D073D5123456", "d073d5-123456",
                     "d0 73 d5 12 34 56"):
            self.assertEqual(p.normalize_serial(text), "d073d5123456")

    def test_normalize_rejects_wrong_length(self):
        for text in ("", None, "d073d5", "d073d51234567", "zzzzzzzzzzzz"):
            self.assertIsNone(p.normalize_serial(text))

    def test_invalid_serial_raises(self):
        with self.assertRaises(p.ProtocolError):
            p.serial_to_target("nope")


class TestPayloads(unittest.TestCase):

    def test_set_color_is_thirteen_bytes(self):
        payload = p.payload_set_color(100, 200, 300, 3500, 1000)
        self.assertEqual(len(payload), 13)
        reserved, h, s, b, k, duration = struct.unpack("<BHHHHI", payload)
        self.assertEqual((reserved, h, s, b, k, duration),
                         (0, 100, 200, 300, 3500, 1000))

    def test_set_power_is_six_bytes_and_uses_full_scale(self):
        on = p.payload_set_power(True, 400)
        off = p.payload_set_power(False, 0)
        self.assertEqual(len(on), 6)
        self.assertEqual(struct.unpack("<HI", on), (65535, 400))
        self.assertEqual(struct.unpack("<HI", off), (0, 0))

    def test_negative_duration_is_floored_at_zero(self):
        self.assertEqual(struct.unpack("<HI", p.payload_set_power(True, -5))[1], 0)


class TestParsers(unittest.TestCase):

    def _light_state(self, label, hue=0, sat=0, bri=65535, kelvin=3500, power=65535):
        return struct.pack("<HHHHhH32sQ", hue, sat, bri, kelvin, 0, power, label, 0)

    def test_light_state_payload_is_52_bytes(self):
        self.assertEqual(len(self._light_state(b"x")), 52)

    def test_light_state_nul_padded_label(self):
        payload = self._light_state(b"Kitchen Sink\x00" + b"\x00" * 19,
                                    hue=21845, sat=65535, bri=32768, kelvin=2700)
        out = p.parse_light_state(payload)
        self.assertEqual(out["label"], "Kitchen Sink")
        self.assertEqual(out["hue"], 21845)
        self.assertEqual(out["saturation"], 65535)
        self.assertEqual(out["brightness"], 32768)
        self.assertEqual(out["kelvin"], 2700)
        self.assertTrue(out["power"])

    def test_light_state_full_width_label_without_terminator(self):
        """A 32-char label fills the field with no NUL - must not lose a character."""
        label = b"A" * 32
        out = p.parse_light_state(self._light_state(label))
        self.assertEqual(out["label"], "A" * 32)

    def test_light_state_power_zero_is_off(self):
        self.assertFalse(p.parse_light_state(self._light_state(b"x", power=0))["power"])

    def test_state_service(self):
        out = p.parse_state_service(struct.pack("<BI", 1, 56700))
        self.assertEqual(out, {"service": 1, "port": 56700})

    def test_state_group_is_56_bytes(self):
        gid = bytes(range(16))
        payload = struct.pack("<16s32sQ", gid, b"Living Room", 1234567890)
        self.assertEqual(len(payload), 56)
        out = p.parse_state_group(payload)
        self.assertEqual(out["group_id"], gid.hex())
        self.assertEqual(out["label"], "Living Room")
        self.assertEqual(out["updated_at"], 1234567890)

    def test_state_location_uses_its_own_key(self):
        payload = struct.pack("<16s32sQ", bytes(16), b"Home", 5)
        self.assertEqual(p.parse_state_location(payload)["location_id"], "00" * 16)

    def test_state_version_ignores_deprecated_trailing_field(self):
        payload = struct.pack("<III", 1, 55, 999)
        self.assertEqual(len(payload), 12)
        self.assertEqual(p.parse_state_version(payload), {"vendor": 1, "product": 55})

    def test_truncated_payloads_raise_protocol_error_not_struct_error(self):
        cases = [
            (p.parse_state_service, b"\x01"),
            (p.parse_light_state, b"\x00" * 51),
            (p.parse_state_group, b"\x00" * 55),
            (p.parse_state_location, b"\x00" * 10),
            (p.parse_state_version, b"\x00" * 11),
            (p.parse_state_power, b"\x00"),
        ]
        for parser, payload in cases:
            with self.assertRaises(p.ProtocolError):
                parser(payload)

    def test_parse_payload_dispatch_and_unknown_type(self):
        self.assertEqual(
            p.parse_payload(p.STATE_SERVICE, struct.pack("<BI", 1, 56700))["port"],
            56700)
        self.assertIsNone(p.parse_payload(p.ACKNOWLEDGEMENT, b""))


class TestColour(unittest.TestCase):

    def test_hsbk_pct_round_trip(self):
        for hue, sat, bri, kelvin in [(0, 0, 0, 1500), (180, 50, 50, 3500),
                                      (359, 100, 100, 9000), (270, 25, 75, 2700)]:
            raw = p.hsbk_from_pct(hue, sat, bri, kelvin)
            back = p.hsbk_to_pct(*raw)
            self.assertAlmostEqual(back[0], hue, delta=0.02)
            self.assertAlmostEqual(back[1], sat, delta=0.02)
            self.assertAlmostEqual(back[2], bri, delta=0.02)
            self.assertEqual(back[3], kelvin)

    def test_hue_360_wraps_to_zero(self):
        self.assertEqual(p.hsbk_from_pct(360, 0, 0, 3500)[0], 0)

    def test_out_of_range_values_are_clamped(self):
        h, s, b, k = p.hsbk_from_pct(0, 500, -20, 99999)
        self.assertEqual((s, b, k), (p.U16, 0, p.KELVIN_MAX))

    def test_clamp_kelvin_handles_garbage(self):
        self.assertEqual(p.clamp_kelvin("nonsense"), 3500)
        self.assertEqual(p.clamp_kelvin(None), 3500)
        self.assertEqual(p.clamp_kelvin(500), p.KELVIN_MIN)

    def test_zero_saturation_uses_the_blackbody_curve(self):
        """A LIFX bulb at sat=0 emits white at `kelvin`, not HSV grey."""
        for kelvin in (1500, 2700, 4000, 6500, 9000):
            self.assertEqual(p.hsbk_to_rgb(0, 0, p.U16, kelvin),
                             p.kelvin_to_rgb(kelvin))

    def test_zero_saturation_scales_by_brightness(self):
        full = p.kelvin_to_rgb(2700)
        half = p.hsbk_to_rgb(0, 0, p.U16 // 2, 2700)
        for channel_full, channel_half in zip(full, half):
            self.assertAlmostEqual(channel_half, channel_full / 2.0, delta=1.5)

    def test_saturated_red(self):
        raw = p.hsbk_from_pct(0, 100, 100, 3500)
        self.assertEqual(p.hsbk_to_rgb(*raw), (255, 0, 0))

    def test_kelvin_to_rgb_monotonicity(self):
        """Red never rises and blue never falls as the temperature climbs."""
        samples = [p.kelvin_to_rgb(k) for k in range(1500, 9001, 100)]
        reds = [c[0] for c in samples]
        blues = [c[2] for c in samples]
        self.assertEqual(reds, sorted(reds, reverse=True))
        self.assertEqual(blues, sorted(blues))
        self.assertTrue(all(0 <= v <= 255 for c in samples for v in c))

    def test_rgb_to_hsbk_round_trip(self):
        for rgb in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 136, 0)]:
            self.assertEqual(p.hsbk_to_rgb(*p.rgb_to_hsbk(*rgb)), rgb)


class TestColourStrings(unittest.TestCase):

    def test_hex_forms(self):
        for text in ("#ff8800", "FF8800", "ff8800", "#F80"):
            out = p.parse_color_string(text)
            self.assertIsNotNone(out, text)
            self.assertAlmostEqual(out["hue"], 32.0, delta=1.0)
            self.assertAlmostEqual(out["saturation"], 100.0, delta=0.5)
            self.assertAlmostEqual(out["brightness"], 100.0, delta=0.5)

    def test_named_colour(self):
        out = p.parse_color_string("red")
        self.assertAlmostEqual(out["hue"], 0.0)
        self.assertAlmostEqual(out["saturation"], 100.0)

    def test_kelvin_string_leaves_brightness_alone(self):
        out = p.parse_color_string("3500k")
        self.assertEqual(out["kelvin"], 3500)
        self.assertEqual(out["saturation"], 0.0)
        self.assertIsNone(out["brightness"],
                          "a kelvin string must not force a brightness")

    def test_kelvin_string_is_clamped(self):
        self.assertEqual(p.parse_color_string("99000k")["kelvin"], p.KELVIN_MAX)

    def test_kelvin_words(self):
        self.assertEqual(p.parse_color_string("candle")["kelvin"], 1500)
        self.assertEqual(p.parse_color_string("warm white")["kelvin"], 2700)

    def test_unparseable_returns_none(self):
        for text in ("nonsense", "", None, "#12345", "zzzzzz"):
            self.assertIsNone(p.parse_color_string(text), repr(text))


class TestProducts(unittest.TestCase):

    def test_known_colour_bulb(self):
        info = p.product_info(27)
        self.assertTrue(info["color"])
        self.assertEqual(info["kelvin"], (2500, 9000))

    def test_known_white_only_bulb(self):
        info = p.product_info(10)          # White 800
        self.assertFalse(info["color"])
        self.assertEqual(info["kelvin"], (2700, 6500))

    def test_unknown_product_falls_back_permissively(self):
        info = p.product_info(99999)
        self.assertTrue(info["color"])
        self.assertEqual(info["kelvin"], (p.KELVIN_MIN, p.KELVIN_MAX))

    def test_fallback_is_a_copy_not_the_shared_default(self):
        info = p.product_info(99999)
        info["name"] = "mutated"
        self.assertEqual(p.product_info(88888)["name"], "LIFX")


if __name__ == "__main__":
    unittest.main(verbosity=2)
