"""LIFX LAN UDP transport.

No Kivy and no widget access - safe to drive from any background thread, and
testable against the loopback simulator in ``tests/fakebulb.py``::

    python3 screens/LIFX/tests/test_client.py

Design: **one socket, one reader thread.**  Every caller blocks on its own
``threading.Event`` and the reader demultiplexes replies by the frame's
sequence byte, so the screen's poll loop and an inbound MQTT event can be in
flight at the same time without stepping on each other.

Two filters keep other people's traffic out: frames whose ``source`` is not
ours are dropped (so a LIFX phone app or a Home Assistant instance on the same
LAN is invisible), and each waiter additionally checks the message type and
serial before accepting a datagram.
"""

import random
import socket
import threading
import time

from screens.LIFX import protocol as p

try:  # in-app; falls back to stdlib when tests run outside the project root
    from util.phlog import PIHOME_LOGGER as LOG
except Exception:  # pragma: no cover
    import logging
    LOG = logging.getLogger("pihome.lifx")

_RECV_SIZE = 4096
_SOCKET_POLL = 0.4          # recvfrom timeout, so the reader can notice shutdown
_UNLIMITED = 1 << 30        # "collect everything in the window" for broadcasts


class LifxTimeout(Exception):
    """A bulb did not answer within the timeout after all retries."""


class Device(object):
    """Where to reach one bulb."""

    __slots__ = ("serial", "ip", "port")

    def __init__(self, serial, ip, port=p.LIFX_PORT):
        self.serial = serial
        self.ip = ip
        self.port = int(port or p.LIFX_PORT)

    @property
    def addr(self):
        return (self.ip, self.port)

    def __repr__(self):
        return "Device({}, {}:{})".format(self.serial, self.ip, self.port)

    def __eq__(self, other):
        return (isinstance(other, Device) and other.serial == self.serial
                and other.ip == self.ip and other.port == self.port)

    def __hash__(self):
        return hash((self.serial, self.ip, self.port))


class _Pending(object):
    """One in-flight request waiting on the reader thread."""

    __slots__ = ("event", "responses", "expect_type", "expect_serial", "want")

    def __init__(self, expect_type=None, expect_serial=None, want=1):
        self.event = threading.Event()
        self.responses = []
        self.expect_type = expect_type
        self.expect_serial = expect_serial
        self.want = want

    def matches(self, frame):
        if self.expect_serial and frame.serial != self.expect_serial:
            return False
        if self.expect_type is not None and frame.msg_type != self.expect_type:
            return False
        return True


# ── Transport ─────────────────────────────────────────────────────────────

class LifxTransport(object):

    def __init__(self, source=None, bind_addr="0.0.0.0"):
        # A nonzero source, fixed for the process, is what lets bulbs address
        # their replies back to us specifically rather than broadcasting them.
        self._source = int(source) if source else random.randint(1, 0xFFFFFFFE)
        self._bind_addr = bind_addr
        self._sock = None
        self._thread = None
        self._running = threading.Event()
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._seq_lock = threading.Lock()
        self._sequence = random.randint(0, 255)

    @property
    def source(self):
        return self._source

    @property
    def port(self):
        return self._sock.getsockname()[1] if self._sock else None

    # ── lifecycle ──

    def start(self):
        if self._sock is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Bind an EPHEMERAL port, not 56700: bulbs reply to the source port, and
        # claiming 56700 fights anything else on the host speaking LIFX.
        sock.bind((self._bind_addr, 0))
        sock.settimeout(_SOCKET_POLL)
        self._sock = sock
        self._running.set()
        self._thread = threading.Thread(target=self._reader, daemon=True,
                                        name="lifx-rx")
        self._thread.start()

    def close(self):
        self._running.clear()
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        with self._pending_lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for entry in pending:      # release anyone blocked on a reply
            entry.event.set()

    # ── reader thread ──

    def _reader(self):
        while self._running.is_set():
            sock = self._sock
            if sock is None:
                return
            try:
                data, addr = sock.recvfrom(_RECV_SIZE)
            except socket.timeout:
                continue
            except OSError:
                return                       # socket closed under us: we're done
            try:
                frame = p.unpack(data)
            except p.ProtocolError:
                continue                     # not ours, or corrupt
            if frame.source != self._source:
                continue                     # another LIFX client on this LAN
            self._deliver(frame, addr)

    def _deliver(self, frame, addr):
        with self._pending_lock:
            entry = self._pending.get(frame.sequence)
            if entry is None or not entry.matches(frame):
                return
            entry.responses.append((frame, addr))
            ready = len(entry.responses) >= entry.want
        if ready:
            entry.event.set()

    # ── sequencing ──

    def _next_sequence(self):
        """Roll 0-255, skipping any value a live request is still waiting on."""
        with self._seq_lock:
            for _ in range(256):
                self._sequence = (self._sequence + 1) & 0xFF
                with self._pending_lock:
                    if self._sequence not in self._pending:
                        return self._sequence
            return self._sequence

    def _register(self, sequence, entry):
        with self._pending_lock:
            self._pending[sequence] = entry

    def _unregister(self, sequence):
        with self._pending_lock:
            self._pending.pop(sequence, None)

    def _sendto(self, data, addr):
        sock = self._sock
        if sock is None:
            raise LifxTimeout("LIFX transport is not running")
        with self._send_lock:
            sock.sendto(data, addr)

    # ── public API ──

    def broadcast(self, msg_type, payload=b"", collect_for=1.2,
                  expect_type=None, addresses=None, port=p.LIFX_PORT):
        """Fire a tagged message and collect every reply for *collect_for* seconds.

        Returns ``[(Frame, (ip, port)), ...]``.  Never exits early - discovery
        wants the whole window, not the first bulb to answer.
        """
        addresses = addresses or ["255.255.255.255"]
        sequence = self._next_sequence()
        entry = _Pending(expect_type=expect_type, want=_UNLIMITED)
        self._register(sequence, entry)
        try:
            frame = p.pack(msg_type, payload, source=self._source,
                           sequence=sequence, tagged=True, res_required=True)
            sent = 0
            for address in addresses:
                try:
                    self._sendto(frame, (address, port))
                    sent += 1
                except OSError as exc:
                    # A host with no route for limited broadcast (VPN up, or an
                    # interface down) is normal - the other address may work.
                    LOG.debug("LIFX: broadcast to {} failed: {}".format(address, exc))
            if not sent:
                return []
            entry.event.wait(collect_for)    # want is unreachable: runs the full window
            with self._pending_lock:
                return list(entry.responses)
        finally:
            self._unregister(sequence)

    def request(self, device, msg_type, payload=b"", expect_type=None,
                timeout=0.6, retries=2):
        """Send and block for a typed reply, returning the parsed payload dict."""
        last_error = None
        for attempt in range(retries + 1):
            # A FRESH sequence per attempt: a slow reply to attempt 1 must not
            # be able to satisfy attempt 2's waiter.
            sequence = self._next_sequence()
            entry = _Pending(expect_type=expect_type,
                             expect_serial=device.serial, want=1)
            self._register(sequence, entry)
            try:
                frame = p.pack(msg_type, payload, source=self._source,
                               sequence=sequence, serial=device.serial,
                               res_required=True)
                try:
                    self._sendto(frame, device.addr)
                except OSError as exc:
                    last_error = exc
                    continue
                if entry.event.wait(timeout) and entry.responses:
                    reply = entry.responses[0][0]
                    parsed = p.parse_payload(reply.msg_type, reply.payload)
                    return parsed if parsed is not None else {}
            except p.ProtocolError as exc:
                last_error = exc
            finally:
                self._unregister(sequence)

        raise LifxTimeout(
            "No reply from {} for message {} after {} attempt(s){}".format(
                device.serial, msg_type, retries + 1,
                ": {}".format(last_error) if last_error else ""))

    def command(self, device, msg_type, payload=b"", timeout=0.5,
                retries=2, wait_ack=True):
        """Send a state-changing message.  -> True if it was (or is presumed) applied.

        ``wait_ack=False`` is fire-and-forget, for intermediate frames of a drag
        where a dropped packet is invisible because another follows in ~100ms.
        """
        if not wait_ack:
            sequence = self._next_sequence()
            frame = p.pack(msg_type, payload, source=self._source,
                           sequence=sequence, serial=device.serial)
            try:
                self._sendto(frame, device.addr)
                return True
            except OSError as exc:
                LOG.debug("LIFX: send to {} failed: {}".format(device.serial, exc))
                return False

        for _attempt in range(retries + 1):
            sequence = self._next_sequence()
            entry = _Pending(expect_type=p.ACKNOWLEDGEMENT,
                             expect_serial=device.serial, want=1)
            self._register(sequence, entry)
            try:
                frame = p.pack(msg_type, payload, source=self._source,
                               sequence=sequence, serial=device.serial,
                               ack_required=True)
                try:
                    self._sendto(frame, device.addr)
                except OSError:
                    continue
                if entry.event.wait(timeout) and entry.responses:
                    return True
            finally:
                self._unregister(sequence)
        return False


# ── Address helpers ───────────────────────────────────────────────────────

def local_ip():
    """This host's LAN address, via a UDP socket that never sends anything."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def broadcast_addresses(explicit=""):
    """Where to send discovery.

    Limited broadcast alone is not enough: on a host with several interfaces
    (a Pi on Wi-Fi and Ethernet, a Mac with a VPN up) 255.255.255.255 leaves
    via whichever one the routing table picks, and some consumer APs drop it
    outright.  Sending to the subnet-directed address as well covers both.
    A /24 is assumed - the `broadcast_address` setting exists for the rest.
    """
    explicit = (explicit or "").strip()
    if explicit:
        return [explicit]

    addresses = ["255.255.255.255"]
    ip = local_ip()
    if ip and not ip.startswith("127."):
        parts = ip.split(".")
        if len(parts) == 4:
            directed = "{}.{}.{}.255".format(*parts[:3])
            if directed not in addresses:
                addresses.append(directed)
    return addresses


# ── High-level operations ─────────────────────────────────────────────────

def discover(transport, rounds=3, per_round=1.2, addresses=None,
             port=p.LIFX_PORT):
    """Broadcast GetService a few times and collect the bulbs that answer.

    UDP discovery is lossy, so repeat: a bulb missed in round 1 usually shows
    up in round 2.  -> ``{serial: Device}``
    """
    found = {}
    for _round in range(max(1, rounds)):
        replies = transport.broadcast(
            p.GET_SERVICE, collect_for=per_round,
            expect_type=p.STATE_SERVICE, addresses=addresses, port=port)
        for frame, addr in replies:
            if not frame.serial:
                continue
            try:
                info = p.parse_state_service(frame.payload)
            except p.ProtocolError:
                continue
            if info["service"] != 1:        # 1 = UDP; ignore reserved services
                continue
            found[frame.serial] = Device(frame.serial, addr[0],
                                         info["port"] or port)
    return found


def get_light_state(transport, device, timeout=0.6, retries=2):
    """-> {"hue", "saturation", "brightness", "kelvin", "power", "label"}"""
    return transport.request(device, p.LIGHT_GET, expect_type=p.LIGHT_STATE,
                             timeout=timeout, retries=retries)


def fetch_metadata(transport, device, timeout=0.6):
    """Build a full registry entry for one bulb.

    The light state is required - without it there is nothing to show.  Group,
    location and version are best-effort: a bulb that is slow to answer those
    still belongs in the list, just under "Ungrouped" with default capabilities.
    """
    state = get_light_state(transport, device, timeout=timeout)

    entry = {
        "serial": device.serial,
        "ip": device.ip,
        "port": device.port,
        "label": state.get("label") or device.serial,
        "group": "",
        "group_id": "",
        "location": "",
        "location_id": "",
        "product": 0,
        "color": True,
        "kelvin_range": [p.KELVIN_MIN, p.KELVIN_MAX],
        "hue": state.get("hue", 0),
        "saturation": state.get("saturation", 0),
        "brightness": state.get("brightness", 0),
        "kelvin": state.get("kelvin", 3500),
        "power": bool(state.get("power")),
        "seen_at": time.time(),
        "online": True,
    }

    try:
        group = transport.request(device, p.GET_GROUP, expect_type=p.STATE_GROUP,
                                  timeout=timeout, retries=1)
        entry["group"] = group.get("label") or ""
        entry["group_id"] = group.get("group_id") or ""
    except LifxTimeout:
        LOG.debug("LIFX: {} did not report its group".format(device.serial))

    try:
        location = transport.request(device, p.GET_LOCATION,
                                     expect_type=p.STATE_LOCATION,
                                     timeout=timeout, retries=1)
        entry["location"] = location.get("label") or ""
        entry["location_id"] = location.get("location_id") or ""
    except LifxTimeout:
        LOG.debug("LIFX: {} did not report its location".format(device.serial))

    try:
        version = transport.request(device, p.GET_VERSION,
                                    expect_type=p.STATE_VERSION,
                                    timeout=timeout, retries=1)
        info = p.product_info(version.get("product", 0))
        entry["product"] = version.get("product", 0)
        entry["color"] = info["color"]
        entry["kelvin_range"] = list(info["kelvin"])
    except LifxTimeout:
        LOG.debug("LIFX: {} did not report its product".format(device.serial))

    return entry


def set_color(transport, device, hsbk, duration_ms=0, wait_ack=True, retries=2):
    """*hsbk* is a raw u16 4-tuple as produced by ``protocol.hsbk_from_pct``."""
    hue, saturation, brightness, kelvin = hsbk
    payload = p.payload_set_color(hue, saturation, brightness, kelvin, duration_ms)
    return transport.command(device, p.LIGHT_SET_COLOR, payload,
                             wait_ack=wait_ack, retries=retries)


def set_power(transport, device, on, duration_ms=0, wait_ack=True, retries=2):
    payload = p.payload_set_power(bool(on), duration_ms)
    return transport.command(device, p.LIGHT_SET_POWER, payload,
                             wait_ack=wait_ack, retries=retries)
