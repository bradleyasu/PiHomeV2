"""Headless tests for the LIFX UDP transport, driven by a loopback bulb.

No real hardware, no Kivy:

    python3 screens/LIFX/tests/test_client.py
"""

import os
import socket
import sys
import threading
import time
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from screens.LIFX import client as c  # noqa: E402
from screens.LIFX import protocol as p  # noqa: E402
from screens.LIFX.tests.fakebulb import FakeBulb  # noqa: E402

LOOPBACK = ["127.0.0.1"]


class TransportCase(unittest.TestCase):
    """Starts a transport and tears it (and any bulbs) down afterwards."""

    def setUp(self):
        self.transport = c.LifxTransport(bind_addr="127.0.0.1")
        self.transport.start()
        self.bulbs = []

    def tearDown(self):
        self.transport.close()
        for bulb in self.bulbs:
            bulb.stop()

    def bulb(self, **kwargs):
        bulb = FakeBulb(**kwargs).start()
        self.bulbs.append(bulb)
        return bulb

    def device(self, bulb):
        return c.Device(bulb.serial, bulb.host, bulb.port)


class TestDiscovery(TransportCase):

    def test_finds_a_bulb(self):
        bulb = self.bulb(label="Sink")
        found = c.discover(self.transport, rounds=1, per_round=0.6,
                           addresses=LOOPBACK, port=bulb.port)
        self.assertIn(bulb.serial, found)
        device = found[bulb.serial]
        self.assertEqual(device.ip, "127.0.0.1")
        self.assertEqual(device.port, bulb.port)

    def test_finds_several_bulbs_on_one_port(self):
        """Two bulbs answering the same broadcast must both survive the window."""
        first = self.bulb(serial="d073d5000001", label="Sink")
        second = self.bulb(serial="d073d5000002", label="Island",
                           port=first.port + 1)
        found = {}
        for bulb in (first, second):
            found.update(c.discover(self.transport, rounds=1, per_round=0.5,
                                    addresses=LOOPBACK, port=bulb.port))
        self.assertEqual(sorted(found), ["d073d5000001", "d073d5000002"])

    def test_lossy_discovery_recovers_on_a_later_round(self):
        bulb = self.bulb(drop_first=1)
        found = c.discover(self.transport, rounds=3, per_round=0.4,
                           addresses=LOOPBACK, port=bulb.port)
        self.assertIn(bulb.serial, found)

    def test_no_bulbs_returns_empty(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
        sock.close()
        found = c.discover(self.transport, rounds=1, per_round=0.3,
                           addresses=LOOPBACK, port=dead_port)
        self.assertEqual(found, {})


class TestRequest(TransportCase):

    def test_light_state_round_trip(self):
        bulb = self.bulb(label="Sink")
        bulb.hue, bulb.saturation, bulb.brightness = 21845, p.U16, 32768
        state = c.get_light_state(self.transport, self.device(bulb))
        self.assertEqual(state["label"], "Sink")
        self.assertEqual(state["hue"], 21845)
        self.assertEqual(state["brightness"], 32768)
        self.assertTrue(state["power"])

    def test_retries_then_succeeds(self):
        bulb = self.bulb(drop_first=2)
        state = c.get_light_state(self.transport, self.device(bulb),
                                  timeout=0.3, retries=2)
        self.assertEqual(state["label"], "Test Bulb")

    def test_timeout_after_all_retries(self):
        bulb = self.bulb(drop_first=99)
        with self.assertRaises(c.LifxTimeout):
            c.get_light_state(self.transport, self.device(bulb),
                              timeout=0.2, retries=1)

    def test_metadata_gathers_group_location_and_product(self):
        bulb = self.bulb(label="Sink", group="Kitchen", location="Home",
                         product=10)      # White 800: no colour, 2700-6500
        entry = c.fetch_metadata(self.transport, self.device(bulb))
        self.assertEqual(entry["label"], "Sink")
        self.assertEqual(entry["group"], "Kitchen")
        self.assertEqual(entry["location"], "Home")
        self.assertEqual(entry["product"], 10)
        self.assertFalse(entry["color"])
        self.assertEqual(entry["kelvin_range"], [2700, 6500])
        self.assertTrue(entry["online"])

    def test_metadata_survives_a_bulb_that_only_answers_light_get(self):
        """Group/location/version are best-effort - the bulb still belongs in the list."""
        bulb = self.bulb(label="Quiet")

        original = bulb._respond

        def only_light_get(frame):
            if frame.msg_type in (p.GET_GROUP, p.GET_LOCATION, p.GET_VERSION):
                return []
            return original(frame)

        bulb._respond = only_light_get
        entry = c.fetch_metadata(self.transport, self.device(bulb), timeout=0.15)
        self.assertEqual(entry["label"], "Quiet")
        self.assertEqual(entry["group"], "")
        self.assertTrue(entry["color"])          # permissive default


class TestCommands(TransportCase):

    def test_set_color_is_acked_and_applied(self):
        bulb = self.bulb()
        hsbk = p.hsbk_from_pct(120, 100, 50, 3500)
        self.assertTrue(c.set_color(self.transport, self.device(bulb), hsbk, 400))
        self.assertEqual(bulb.hue, hsbk[0])
        self.assertEqual(bulb.saturation, hsbk[1])
        self.assertEqual(bulb.brightness, hsbk[2])

    def test_set_power_off_then_on(self):
        bulb = self.bulb()
        self.assertTrue(c.set_power(self.transport, self.device(bulb), False))
        self.assertFalse(bulb.power)
        self.assertTrue(c.set_power(self.transport, self.device(bulb), True))
        self.assertTrue(bulb.power)

    def test_command_returns_false_when_never_acked(self):
        bulb = self.bulb(drop_first=99)
        self.assertFalse(c.set_power(self.transport, self.device(bulb), False,
                                     retries=1))

    def test_fire_and_forget_does_not_wait_for_an_ack(self):
        """Intermediate drag frames use wait_ack=False; a drop is invisible."""
        bulb = self.bulb(drop_first=99)
        self.assertTrue(c.set_power(self.transport, self.device(bulb), False,
                                    wait_ack=False))

    def test_ack_is_requested_only_when_waiting(self):
        """Fire-and-forget sends exactly one datagram and never retries."""
        bulb = self.bulb()
        c.set_power(self.transport, self.device(bulb), True, wait_ack=False)
        # The call returns as soon as the datagram is out, so give the bulb's
        # thread a moment to actually pick it up before counting.
        deadline = time.monotonic() + 2.0
        while not bulb.received and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(bulb.received, [p.LIGHT_SET_POWER])
        self.assertTrue(bulb.power)


class TestConcurrency(TransportCase):

    def test_two_threads_get_their_own_replies(self):
        """The whole point of sequence demux: no cross-talk between callers."""
        first = self.bulb(serial="d073d5000001", label="Sink", delay=0.05)
        second = self.bulb(serial="d073d5000002", label="Island",
                           port=first.port + 1, delay=0.05)
        results = {}

        def fetch(bulb):
            results[bulb.serial] = c.get_light_state(
                self.transport, self.device(bulb), timeout=1.5)["label"]

        threads = [threading.Thread(target=fetch, args=(b,))
                   for b in (first, second)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertEqual(results, {"d073d5000001": "Sink",
                                   "d073d5000002": "Island"})

    def test_concurrent_requests_of_different_types_to_one_bulb(self):
        bulb = self.bulb(label="Sink", group="Kitchen", delay=0.05)
        device = self.device(bulb)
        results = {}

        def light():
            results["light"] = self.transport.request(
                device, p.LIGHT_GET, expect_type=p.LIGHT_STATE,
                timeout=1.5)["label"]

        def group():
            results["group"] = self.transport.request(
                device, p.GET_GROUP, expect_type=p.STATE_GROUP,
                timeout=1.5)["label"]

        threads = [threading.Thread(target=light), threading.Thread(target=group)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertEqual(results, {"light": "Sink", "group": "Kitchen"})


class TestFiltering(TransportCase):

    def test_frames_from_another_lifx_client_are_ignored(self):
        """A phone app or Home Assistant on the same LAN must not satisfy our waiter."""
        bulb = self.bulb(drop_first=99)      # the real bulb stays silent
        device = self.device(bulb)

        foreign = p.pack(
            p.LIGHT_STATE,
            bulb._light_state(),
            source=self.transport.source ^ 0xFFFF,   # a different client
            sequence=0, serial=bulb.serial, tagged=False)

        stop = threading.Event()

        def spam():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            while not stop.is_set():
                for sequence in range(256):
                    frame = bytearray(foreign)
                    frame[23] = sequence             # every possible sequence byte
                    sock.sendto(bytes(frame),
                                ("127.0.0.1", self.transport.port))
                stop.wait(0.02)
            sock.close()

        thread = threading.Thread(target=spam, daemon=True)
        thread.start()
        try:
            with self.assertRaises(c.LifxTimeout):
                c.get_light_state(self.transport, device, timeout=0.3, retries=1)
        finally:
            stop.set()
            thread.join(timeout=2)

    def test_reply_from_the_wrong_serial_is_ignored(self):
        first = self.bulb(serial="d073d5000001", label="Sink")
        wrong = c.Device("d073d5009999", first.host, first.port)
        with self.assertRaises(c.LifxTimeout):
            c.get_light_state(self.transport, wrong, timeout=0.3, retries=0)


class TestTransportLifecycle(unittest.TestCase):

    def test_source_is_nonzero_and_stable(self):
        transport = c.LifxTransport()
        self.assertNotEqual(transport.source, 0)
        self.assertEqual(transport.source, transport.source)

    def test_binds_an_ephemeral_port_not_56700(self):
        transport = c.LifxTransport(bind_addr="127.0.0.1")
        transport.start()
        try:
            self.assertNotEqual(transport.port, p.LIFX_PORT)
            self.assertGreater(transport.port, 0)
        finally:
            transport.close()

    def test_start_is_idempotent(self):
        transport = c.LifxTransport(bind_addr="127.0.0.1")
        transport.start()
        port = transport.port
        transport.start()
        try:
            self.assertEqual(transport.port, port)
        finally:
            transport.close()

    def test_close_stops_the_reader_thread(self):
        transport = c.LifxTransport(bind_addr="127.0.0.1")
        transport.start()
        thread = transport._thread
        transport.close()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())

    def test_close_is_safe_twice(self):
        transport = c.LifxTransport(bind_addr="127.0.0.1")
        transport.start()
        transport.close()
        transport.close()

    def test_sequence_never_reuses_a_live_one(self):
        transport = c.LifxTransport(bind_addr="127.0.0.1")
        transport.start()
        try:
            held = [transport._next_sequence() for _ in range(8)]
            for sequence in held:
                transport._register(sequence, c._Pending())
            self.assertNotIn(transport._next_sequence(), held)
        finally:
            transport.close()


class TestBroadcastAddresses(unittest.TestCase):

    def test_explicit_address_wins(self):
        self.assertEqual(c.broadcast_addresses("192.168.5.255"), ["192.168.5.255"])
        self.assertEqual(c.broadcast_addresses("  10.0.0.255  "), ["10.0.0.255"])

    def test_auto_includes_limited_broadcast(self):
        """Limited broadcast alone misses bulbs on multi-interface hosts."""
        addresses = c.broadcast_addresses("")
        self.assertIn("255.255.255.255", addresses)
        self.assertLessEqual(len(addresses), 2)
        for address in addresses:
            self.assertTrue(address.endswith(".255"), address)


if __name__ == "__main__":
    unittest.main(verbosity=2)
