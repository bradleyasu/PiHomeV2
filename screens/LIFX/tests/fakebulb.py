"""A loopback LIFX bulb, for exercising the transport without hardware.

Speaks just enough of the protocol to answer discovery, report state and
acknowledge writes.  It can also drop the first N datagrams, which is how the
retry path gets tested deterministically.

Not a test itself - imported by ``test_client.py``.
"""

import os
import socket
import struct
import sys
import threading

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from screens.LIFX import protocol as p  # noqa: E402


class FakeBulb(object):

    def __init__(self, serial="d073d5000001", label="Test Bulb", group="Kitchen",
                 location="Home", product=27, host="127.0.0.1", port=0,
                 drop_first=0, delay=0.0):
        self.serial = serial
        self.label = label
        self.group = group
        self.location = location
        self.product = product
        self.host = host
        self.drop_first = drop_first
        self.delay = delay

        # Mutable state the transport can read back after a write.
        self.hue = 0
        self.saturation = 0
        self.brightness = p.U16
        self.kelvin = 3500
        self.power = True

        self.received = []          # message types seen, in order
        self.dropped = 0

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, port))
        self._sock.settimeout(0.2)
        self._running = threading.Event()
        self._thread = None

    @property
    def port(self):
        return self._sock.getsockname()[1]

    # ── lifecycle ──

    def start(self):
        self._running.set()
        self._thread = threading.Thread(target=self._serve, daemon=True,
                                        name="fakebulb-{}".format(self.serial))
        self._thread.start()
        return self

    def stop(self):
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # ── serving ──

    def _serve(self):
        while self._running.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                frame = p.unpack(data)
            except p.ProtocolError:
                continue

            self.received.append(frame.msg_type)

            if self.dropped < self.drop_first:
                self.dropped += 1
                continue

            if self.delay:
                if not self._running.wait(self.delay):
                    pass                     # sleep that still notices shutdown

            for msg_type, payload in self._respond(frame):
                reply = p.pack(msg_type, payload, source=frame.source,
                               sequence=frame.sequence, serial=self.serial,
                               tagged=False)
                try:
                    self._sock.sendto(reply, addr)
                except OSError:
                    return

    def _respond(self, frame):
        """-> [(msg_type, payload), ...] for one received frame."""
        out = []

        if frame.msg_type == p.GET_SERVICE:
            out.append((p.STATE_SERVICE, struct.pack("<BI", 1, self.port)))

        elif frame.msg_type == p.LIGHT_GET:
            out.append((p.LIGHT_STATE, self._light_state()))

        elif frame.msg_type == p.GET_GROUP:
            out.append((p.STATE_GROUP, self._labelled(self.group, b"\x11" * 16)))

        elif frame.msg_type == p.GET_LOCATION:
            out.append((p.STATE_LOCATION, self._labelled(self.location, b"\x22" * 16)))

        elif frame.msg_type == p.GET_VERSION:
            out.append((p.STATE_VERSION, struct.pack("<III", 1, self.product, 0)))

        elif frame.msg_type == p.LIGHT_SET_COLOR:
            _res, hue, sat, bri, kelvin, _dur = struct.unpack("<BHHHHI",
                                                              frame.payload[:13])
            self.hue, self.saturation = hue, sat
            self.brightness, self.kelvin = bri, kelvin
            if frame.ack_required:
                out.append((p.ACKNOWLEDGEMENT, b""))
            if frame.res_required:
                out.append((p.LIGHT_STATE, self._light_state()))

        elif frame.msg_type == p.LIGHT_SET_POWER:
            level, _duration = struct.unpack("<HI", frame.payload[:6])
            self.power = level > 0
            if frame.ack_required:
                out.append((p.ACKNOWLEDGEMENT, b""))

        return out

    def _light_state(self):
        return struct.pack("<HHHHhH32sQ", self.hue, self.saturation,
                           self.brightness, self.kelvin, 0,
                           p.U16 if self.power else 0,
                           self.label.encode("utf-8")[:32], 0)

    @staticmethod
    def _labelled(label, uuid):
        return struct.pack("<16s32sQ", uuid, label.encode("utf-8")[:32], 0)
