"""Always-on BLE bridge for user-built hardware.

PiHome is the BLE *central*; the user's board (an Arduino Nano 33 BLE running
ArduinoBLE, or anything else speaking the PiHome GATT contract defined in
screens/BluetoothConnect/protocol.py) is the *peripheral*. bleak has no
peripheral role, so this is the only workable direction -- and it happens to be
the natural role for each device.

The service runs 24/7, independent of whether the BluetoothConnect screen is
open, so a button on a breadboard works whatever PiHome is currently showing.
It owns one dedicated thread running a private asyncio event loop, because
bleak is asyncio and Kivy is not. Calls crossing in from the Kivy main thread
go through asyncio.run_coroutine_threadsafe and return immediately -- nothing
here ever blocks the UI. Callbacks crossing back out hop via
Clock.schedule_once.

Inbound lines are resolved against user-defined bindings (a command token ->
a nested PiHome event), managed by the events in ../events/ over MQTT, HTTP and
WebSocket. Bindings and the paired-device allowlist persist under cache/.

WHY THE ENABLED GATE MATTERS: PihomeEventFactory._build_event_registry() execs
every screens/*/events/*.py with no manifest or "disabled" check, so this
module is imported -- and this class constructed -- as soon as anything asks
for an event definition, even on installs where the screen is unused. The radio
is therefore never touched until [bluetoothconnect] enabled is set to 1.
"""

import asyncio
import collections
import json
import os
import sys
import threading
import time

from kivy.clock import Clock

from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER

from screens.BluetoothConnect.protocol import (
    AUTH_OK,
    DEFAULT_INFO_UUID,
    DEFAULT_RX_UUID,
    DEFAULT_SERVICE_UUID,
    DEFAULT_TX_UUID,
    LineAssembler,
    chunk,
    normalize_uuid,
    parse_command,
    substitute,
)

try:
    from bleak import BleakClient, BleakScanner

    # bleak logs every advertisement it sees at DEBUG. A scan in a busy room is
    # thousands of lines, which is real overhead on a Pi, so keep it to warnings.
    import logging
    logging.getLogger("bleak").setLevel(logging.WARNING)
except Exception:  # ImportError, or any transitive import error
    BleakClient = None
    BleakScanner = None

_DEVICES_FILE = "cache/bluetooth_devices.json"
_BINDINGS_FILE = "cache/bluetooth_bindings.json"

# Seconds of silence after which a partial line is flushed anyway. Forgetting
# the trailing "\n" is the most common first-sketch mistake; this makes it work
# instead of silently swallowing every command.
_IDLE_FLUSH = 0.15

# How many inbound lines the screen's live log remembers.
_RECENT_MAX = 50

# Reconnect backoff bounds, in seconds.
_BACKOFF_MIN = 5
_BACKOFF_MAX = 60


class BleService:

    def __init__(self):
        self._lock = threading.RLock()
        self._loop = None
        self._async_stop = None
        self._connect_lock = None
        self._scan_lock = None

        self._devices = self._load_json(_DEVICES_FILE, {})    # address -> {address, name, paired_at}
        self._bindings = self._load_json(_BINDINGS_FILE, {})  # "device|command" -> binding

        self._state = {}          # address -> live connection state
        self._recent = collections.deque(maxlen=_RECENT_MAX)
        self._listeners = []
        self._scanning = False
        self._last_error = ""

        # Loop-thread-only structures.
        self._clients = {}
        self._workers = {}
        self._assemblers = {}
        self._flush_handles = {}
        self._disconnect_events = {}
        self._authed = set()
        self._debounce = {}       # (address, command) -> monotonic ts

        if self.available:
            self._thread = threading.Thread(
                target=self._thread_main, daemon=True, name="ble-service"
            )
            self._thread.start()
        else:
            self._thread = None
            PIHOME_LOGGER.warn(
                "Bluetooth: 'bleak' is not installed -- the BLE bridge is idle. "
                "PiHome installs it automatically; a restart is required to pick it up."
            )

    @property
    def available(self):
        return BleakClient is not None

    # ── Configuration ────────────────────────────────────────────────────────

    def _cfg(self):
        """Read every setting fresh so changes apply without a restart."""
        g = lambda key, default: CONFIG.get("bluetoothconnect", key, default).strip()
        return {
            "enabled": g("enabled", "0").lower() in ("1", "true"),
            "notify": g("notify_on_command", "0").lower() in ("1", "true"),
            "max_devices": min(4, max(1, CONFIG.get_int("bluetoothconnect", "max_devices", 2))),
            "scan_seconds": min(30, max(3, CONFIG.get_int("bluetoothconnect", "scan_seconds", 8))),
            "debounce_ms": max(0, CONFIG.get_int("bluetoothconnect", "debounce_ms", 250)),
            "pair_key": g("pair_key", ""),
            "adapter": g("adapter", ""),
            "service_uuid": normalize_uuid(g("service_uuid", ""), DEFAULT_SERVICE_UUID),
            "tx_uuid": normalize_uuid(g("tx_uuid", ""), DEFAULT_TX_UUID),
            "rx_uuid": normalize_uuid(g("rx_uuid", ""), DEFAULT_RX_UUID),
            "info_uuid": normalize_uuid(g("info_uuid", ""), DEFAULT_INFO_UUID),
        }

    def _kw(self, cfg):
        """bleak kwargs that only exist on the BlueZ backend."""
        if sys.platform.startswith("linux") and cfg["adapter"]:
            return {"adapter": cfg["adapter"]}
        return {}

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_json(self, path, default):
        try:
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f) or default
        except Exception as e:
            PIHOME_LOGGER.error(f"Bluetooth: failed to read {path}: {e}")
        return default

    def _save_json(self, path, data):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            PIHOME_LOGGER.error(f"Bluetooth: failed to write {path}: {e}")

    # ── Event loop ───────────────────────────────────────────────────────────

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._supervisor())
        except Exception as e:
            PIHOME_LOGGER.error(f"Bluetooth: event loop stopped: {e}")
        finally:
            try:
                pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            self._loop = None

    def _submit(self, coro):
        """Hand a coroutine to the BLE loop from any thread. Never blocks."""
        loop = self._loop
        if loop is None or loop.is_closed():
            coro.close()
            return False
        try:
            asyncio.run_coroutine_threadsafe(coro, loop)
            return True
        except Exception as e:
            PIHOME_LOGGER.error(f"Bluetooth: could not schedule work: {e}")
            return False

    async def _sleep(self, seconds):
        """Interruptible sleep -- wakes early when shutdown is requested."""
        try:
            await asyncio.wait_for(self._async_stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def _supervisor(self):
        # These must be created on the loop, not in __init__.
        self._async_stop = asyncio.Event()
        self._connect_lock = asyncio.Lock()
        self._scan_lock = asyncio.Lock()

        while not self._async_stop.is_set():
            try:
                cfg = self._cfg()
                if cfg["enabled"]:
                    self._reconcile(cfg)
                elif self._workers:
                    await self._teardown()
            except Exception as e:
                PIHOME_LOGGER.error(f"Bluetooth: supervisor error: {e}")
            await self._sleep(2)

        await self._teardown()

    def _reconcile(self, cfg):
        """Keep exactly one worker task per allowlisted device."""
        with self._lock:
            wanted = list(self._devices.keys())[: cfg["max_devices"]]

        for address in wanted:
            task = self._workers.get(address)
            if task is None or task.done():
                self._workers[address] = asyncio.ensure_future(self._device_worker(address))

        for address, task in list(self._workers.items()):
            if address not in wanted:
                if not task.done():
                    task.cancel()
                self._workers.pop(address, None)

    async def _teardown(self):
        for address, task in list(self._workers.items()):
            if not task.done():
                task.cancel()
            self._workers.pop(address, None)
        for address, client in list(self._clients.items()):
            try:
                await client.disconnect()
            except Exception:
                pass
            self._clients.pop(address, None)
            self._mark(address, connected=False)

    # ── Per-device connection worker ─────────────────────────────────────────

    async def _device_worker(self, address):
        """Own one device's link for the life of the pairing.

        One task per device so a single out-of-range board's backoff never
        starves the others.
        """
        backoff = _BACKOFF_MIN
        while not self._async_stop.is_set():
            # Active discovery destabilizes existing links on a Pi 3's combo
            # chip, so hold off while a scan is running.
            if self._scan_lock.locked():
                await self._sleep(1)
                continue

            cfg = self._cfg()
            if not cfg["enabled"]:
                return

            client = None
            try:
                device = await BleakScanner.find_device_by_address(
                    address, timeout=8.0, **self._kw(cfg)
                )
                # BlueZ serializes connects badly -- two at once yields
                # org.bluez.Error.InProgress.
                async with self._connect_lock:
                    client = BleakClient(
                        device or address,
                        disconnected_callback=lambda c, a=address: self._on_disconnected(a),
                        timeout=15.0,
                        **self._kw(cfg),
                    )
                    await client.connect()

                self._require_chars(client, cfg)

                event = asyncio.Event()
                self._disconnect_events[address] = event
                self._assemblers[address] = LineAssembler()
                self._authed.discard(address)

                await client.start_notify(
                    cfg["tx_uuid"],
                    lambda sender, data, a=address: self._on_notify(a, sender, data),
                )
                self._clients[address] = client

                await self._read_info(client, cfg, address)

                if cfg["pair_key"]:
                    await self._write(client, cfg, "AUTH " + cfg["pair_key"])
                else:
                    self._authed.add(address)

                backoff = _BACKOFF_MIN
                self._mark(address, connected=True, error="", last_seen=time.time())
                PIHOME_LOGGER.info(f"Bluetooth: connected to {address}")

                await event.wait()  # park here until the link drops
                PIHOME_LOGGER.info(f"Bluetooth: {address} disconnected")

            except asyncio.CancelledError:
                raise
            except _Incompatible as e:
                self._mark(address, connected=False, error=str(e))
                backoff = _BACKOFF_MAX  # no point retrying hard against wrong firmware
            except Exception as e:
                self._mark(address, connected=False, error=self._friendly(e))
            finally:
                self._clients.pop(address, None)
                self._assemblers.pop(address, None)
                self._disconnect_events.pop(address, None)
                self._authed.discard(address)
                handle = self._flush_handles.pop(address, None)
                if handle is not None:
                    handle.cancel()
                if client is not None:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                self._mark(address, connected=False)

            await self._sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

    def _require_chars(self, client, cfg):
        found = set()
        for service in client.services:
            for characteristic in service.characteristics:
                found.add(str(characteristic.uuid).lower())
        if cfg["tx_uuid"] not in found:
            raise _Incompatible("Device is missing the PiHome TX characteristic")
        if cfg["pair_key"] and cfg["rx_uuid"] not in found:
            raise _Incompatible("Pair Key is set but the device has no RX characteristic")

    async def _read_info(self, client, cfg, address):
        """Best effort -- the info characteristic is optional."""
        try:
            raw = await client.read_gatt_char(cfg["info_uuid"])
            name = raw.decode("utf-8", "replace").strip()
            if name:
                with self._lock:
                    if address in self._devices:
                        self._devices[address]["name"] = name
                        self._save_json(_DEVICES_FILE, self._devices)
        except Exception:
            pass

    def _on_disconnected(self, address):
        """bleak callback, on the loop thread. Must not await or reconnect."""
        event = self._disconnect_events.get(address)
        if event is not None:
            event.set()
        self._mark(address, connected=False)

    @staticmethod
    def _friendly(exc):
        text = str(exc) or exc.__class__.__name__
        low = text.lower()
        if "turned off" in low or "not ready" in low:
            return "Bluetooth adapter is off or blocked"
        if "not found" in low:
            return "Device not found -- out of range or powered off"
        return text

    # ── Inbound data ─────────────────────────────────────────────────────────

    def _on_notify(self, address, _sender, data):
        """bleak notification callback, on the loop thread.

        Buffering, framing and debounce are all cheap and touch no Kivy state,
        so they happen here; only the actual event dispatch is handed to the
        main thread.
        """
        assembler = self._assemblers.get(address)
        if assembler is None:
            assembler = self._assemblers[address] = LineAssembler()

        try:
            lines = assembler.feed(data)
        except Exception as e:
            PIHOME_LOGGER.error(f"Bluetooth: bad data from {address}: {e}")
            return

        for line in lines:
            self._handle_line(address, line)

        handle = self._flush_handles.pop(address, None)
        if handle is not None:
            handle.cancel()
        if assembler.pending:
            self._flush_handles[address] = self._loop.call_later(
                _IDLE_FLUSH, self._flush_idle, address
            )

    def _flush_idle(self, address):
        self._flush_handles.pop(address, None)
        assembler = self._assemblers.get(address)
        if assembler is None:
            return
        line = assembler.flush()
        if line:
            self._handle_line(address, line)

    def _handle_line(self, address, line):
        cfg = self._cfg()
        self._mark(address, last_seen=time.time())

        if line.strip().lower() == AUTH_OK:
            self._authed.add(address)
            self._mark(address, error="")
            PIHOME_LOGGER.info(f"Bluetooth: {address} completed the pair-key handshake")
            return

        command, value = parse_command(line)
        if not command:
            return

        entry = {
            "ts": time.time(),
            "address": address,
            "name": self._name_of(address),
            "command": command,
            "value": value,
            "result": "",
        }

        if cfg["pair_key"] and address not in self._authed:
            entry["result"] = "ignored -- device has not answered 'AUTH ok'"
            self._push_recent(entry)
            return

        # A bouncing button sends the same token many times in a few ms.
        if cfg["debounce_ms"] > 0:
            key = (address, command)
            now = time.monotonic()
            previous = self._debounce.get(key, 0.0)
            if (now - previous) * 1000.0 < cfg["debounce_ms"]:
                return
            self._debounce[key] = now

        # Logged whether or not it is bound -- this is how a user discovers
        # which tokens their sketch actually emits.
        self._push_recent(entry)
        self._mark(address, last_command=command, last_command_ts=entry["ts"])

        Clock.schedule_once(
            lambda dt, c=command, v=value, a=address, e=entry:
                self.dispatch_command(c, v, address=a, entry=e),
            0,
        )

        if cfg["notify"]:
            Clock.schedule_once(
                lambda dt, c=command: self._toast(f"Bluetooth: {c}", "info", 2), 0
            )

    def _push_recent(self, entry):
        self._recent.appendleft(entry)
        self._notify()

    @staticmethod
    def _toast(message, level, timeout):
        try:
            from util.helpers import toast
            toast(message, level, timeout)
        except Exception:
            pass

    # ── Dispatch (main thread) ───────────────────────────────────────────────

    def dispatch_command(self, command, value=None, address=None, entry=None):
        """Resolve a command token against the bindings and fire the bound event.

        Must be called on the Kivy main thread -- the bound event usually
        touches UI state. The BLE loop reaches this via Clock.schedule_once;
        BluetoothCommandEvent reaches it via the normal event path, which is
        already main-thread.
        """
        token = str(command or "").strip().lower()
        if not token:
            return self._err("'command' is required")

        binding = self._resolve(token, address)
        if binding is None:
            message = f"No binding for command '{token}'"
            if entry is not None:
                entry["result"] = "unbound"
                self._notify()
            return {
                "code": 404,
                "body": {
                    "status": "error",
                    "message": message,
                    "commands": sorted({b["command"] for b in self._bindings.values()}),
                },
            }

        event = binding.get("event")
        if not isinstance(event, dict):
            if entry is not None:
                entry["result"] = "binding has no event"
                self._notify()
            return self._err(f"Binding '{token}' has no valid event")

        try:
            from events.pihomeevent import PihomeEventFactory
            payload = substitute(event, value)
            response = PihomeEventFactory.create_event_from_dict(payload).execute_safe()
        except Exception as e:
            PIHOME_LOGGER.error(f"Bluetooth: command '{token}' failed: {e}")
            if entry is not None:
                entry["result"] = f"failed: {e}"
                self._notify()
            return self._err(f"Command '{token}' failed: {e}")

        if entry is not None:
            entry["result"] = "fired " + str(event.get("type", "?"))
            self._notify()

        return {
            "code": 200,
            "body": {
                "status": "success",
                "message": f"Command '{token}' fired",
                "command": token,
                "value": value,
                "response": (response or {}).get("body"),
            },
        }

    def _resolve(self, token, address):
        """Exact device binding wins over the wildcard."""
        with self._lock:
            if address:
                binding = self._bindings.get(f"{address}|{token}")
                if binding:
                    return binding
            return self._bindings.get(f"*|{token}")

    # ── Bindings ─────────────────────────────────────────────────────────────

    def bind(self, command, event, device=None, description=None):
        token = str(command or "").strip().lower()
        if not token:
            return self._err("'command' is required")
        if not isinstance(event, dict):
            return self._err("'event' must be a nested event object")
        if not event.get("type"):
            return self._err("'event' must contain a 'type'")

        target = str(device).strip() if device else None
        binding = {
            "command": token,
            "device": target,
            "description": str(description).strip() if description else "",
            "event": event,
        }
        with self._lock:
            self._bindings[f"{target or '*'}|{token}"] = binding
            self._save_json(_BINDINGS_FILE, self._bindings)
        self._notify()
        return {
            "code": 200,
            "body": {"status": "success",
                     "message": f"Bound command '{token}'", "binding": binding},
        }

    def unbind(self, command, device=None):
        token = str(command or "").strip().lower()
        if not token:
            return self._err("'command' is required")
        key = f"{str(device).strip() if device else '*'}|{token}"
        with self._lock:
            existed = self._bindings.pop(key, None) is not None
            if existed:
                self._save_json(_BINDINGS_FILE, self._bindings)
        self._notify()
        message = f"Removed binding '{token}'" if existed else f"No binding '{token}'"
        return {"code": 200, "body": {"status": "success", "message": message}}

    def list_bindings(self):
        with self._lock:
            bindings = list(self._bindings.values())
        return {"code": 200, "body": {"status": "success", "bindings": bindings}}

    # ── Paired devices ───────────────────────────────────────────────────────

    def pair(self, address, name=None):
        address = str(address or "").strip()
        if not address:
            return self._err("'address' is required")

        cfg = self._cfg()
        with self._lock:
            if address not in self._devices and len(self._devices) >= cfg["max_devices"]:
                return self._err(
                    f"Already paired with {cfg['max_devices']} devices -- "
                    "forget one first or raise Max Devices in Settings"
                )
            self._devices[address] = {
                "address": address,
                "name": (str(name).strip() if name else None)
                        or self._name_of(address) or "BLE Device",
                "paired_at": time.time(),
            }
            self._save_json(_DEVICES_FILE, self._devices)
            device = self._devices[address]

        self._notify()
        return {"code": 200, "body": {"status": "success",
                "message": f"Paired with {device['name']}", "device": device}}

    def forget(self, address):
        address = str(address or "").strip()
        with self._lock:
            existed = self._devices.pop(address, None) is not None
            if existed:
                self._save_json(_DEVICES_FILE, self._devices)
        self._state.pop(address, None)
        self._notify()
        message = f"Forgot {address}" if existed else f"{address} was not paired"
        return {"code": 200, "body": {"status": "success", "message": message}}

    def list_devices(self):
        return {"code": 200, "body": {"status": "success",
                "devices": self.get_snapshot()["devices"]}}

    # ── Outbound writes ──────────────────────────────────────────────────────

    def send(self, text, address=None):
        text = str(text or "").strip()
        if not text:
            return self._err("'text' is required")
        if not self.available:
            return self._err("Bluetooth support is not installed")

        with self._lock:
            known = list(self._devices.keys())
        if address:
            targets = [str(address).strip()]
        elif len(known) == 1:
            targets = known
        elif not known:
            return self._err("No paired devices")
        else:
            return self._err("'address' is required when more than one device is paired")

        if not self._submit(self._send_all(targets, text)):
            return self._err("Bluetooth service is not running")

        # Queued, not confirmed -- the write happens on the BLE loop.
        return {"code": 202, "body": {"status": "success",
                "message": "Queued", "targets": targets, "text": text}}

    async def _send_all(self, targets, text):
        cfg = self._cfg()
        for address in targets:
            client = self._clients.get(address)
            if client is None:
                PIHOME_LOGGER.warn(f"Bluetooth: cannot send to {address} -- not connected")
                continue
            try:
                await self._write(client, cfg, text)
            except Exception as e:
                PIHOME_LOGGER.error(f"Bluetooth: write to {address} failed: {e}")

    async def _write(self, client, cfg, text):
        """Write a line, chunked so it survives the 23-byte minimum MTU."""
        for part in chunk(text):
            await client.write_gatt_char(cfg["rx_uuid"], part)

    # ── Discovery ────────────────────────────────────────────────────────────

    def start_scan(self, seconds=None, on_found=None, on_complete=None):
        """Begin a discovery scan. Returns immediately; callbacks land on the
        Kivy main thread, matching the NanoleafDiscovery contract."""
        if not self.available or self._scanning:
            return False
        cfg = self._cfg()
        if not cfg["enabled"]:
            return False

        self._scanning = True
        self._notify()
        started = self._submit(
            self._scan(int(seconds or cfg["scan_seconds"]), on_found, on_complete)
        )
        if not started:
            self._scanning = False
        return started

    async def _scan(self, seconds, on_found, on_complete):
        cfg = self._cfg()
        found = {}

        def detected(device, adv):
            address = device.address
            if address in found:
                return
            uuids = {str(u).lower() for u in (adv.service_uuids or [])}
            with self._lock:
                paired = address in self._devices
            entry = {
                "address": address,
                "name": device.name or adv.local_name or "Unknown",
                "rssi": adv.rssi,
                "compatible": cfg["service_uuid"] in uuids,
                "paired": paired,
            }
            found[address] = entry
            if on_found is not None:
                Clock.schedule_once(lambda dt, e=entry: on_found(e), 0)

        try:
            # Deliberately no server-side service_uuids filter: on BlueZ it
            # drops devices that put the 128-bit UUID in the scan response
            # rather than the advertising payload, and it would hide the
            # misconfigured devices this UI exists to diagnose. Filter in
            # `detected` instead and show the rest dimmed.
            async with self._scan_lock:
                scanner = BleakScanner(detection_callback=detected, **self._kw(cfg))
                await scanner.start()
                await self._sleep(seconds)
                try:
                    await scanner.stop()
                except Exception:
                    pass
            self._last_error = ""
        except Exception as e:
            self._last_error = self._friendly(e)
            PIHOME_LOGGER.error(f"Bluetooth: scan failed: {e}")
        finally:
            self._scanning = False
            self._notify()
            if on_complete is not None:
                Clock.schedule_once(
                    lambda dt, d=list(found.values()): on_complete(d), 0
                )

    def stop_scan(self):
        """Best effort -- the scan window ends on its own shortly after."""
        if self._scanning and self._async_stop is not None:
            self._scanning = False
            self._notify()

    # ── Snapshot + listeners ─────────────────────────────────────────────────

    def _name_of(self, address):
        with self._lock:
            device = self._devices.get(address)
        return (device or {}).get("name")

    def _mark(self, address, **fields):
        state = self._state.setdefault(address, {})
        state.update(fields)
        self._notify()

    def get_snapshot(self):
        cfg = self._cfg()
        with self._lock:
            devices = list(self._devices.values())
        rows = []
        for device in devices:
            state = self._state.get(device["address"], {})
            rows.append({
                "address": device["address"],
                "name": device.get("name") or "BLE Device",
                "connected": bool(state.get("connected")),
                "last_seen": state.get("last_seen", 0),
                "last_command": state.get("last_command", ""),
                "last_command_ts": state.get("last_command_ts", 0),
                "error": state.get("error", ""),
            })
        return {
            "available": self.available,
            "enabled": cfg["enabled"],
            "scanning": self._scanning,
            "error": self._last_error,
            "devices": rows,
            "recent": list(self._recent),
            "ts": time.time(),
        }

    def recent_commands(self, limit=25):
        return list(self._recent)[:limit]

    def add_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self):
        if not self._listeners:
            return
        snapshot = self.get_snapshot()
        for callback in list(self._listeners):
            Clock.schedule_once(lambda dt, c=callback: self._safe_cb(c, snapshot), 0)

    @staticmethod
    def _safe_cb(callback, snapshot):
        try:
            callback(snapshot)
        except Exception as e:
            PIHOME_LOGGER.error(f"Bluetooth: listener error: {e}")

    # ── Shutdown ─────────────────────────────────────────────────────────────

    def shutdown(self):
        """Called by util/screen_services.shutdown_screen_services() on exit."""
        loop = self._loop
        if loop is not None and not loop.is_closed() and self._async_stop is not None:
            try:
                loop.call_soon_threadsafe(self._async_stop.set)
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            # on_stop() runs on the main thread -- do not hang the app exit.
            self._thread.join(timeout=3)

    @staticmethod
    def _err(message):
        return {"code": 400, "body": {"status": "error", "message": message}}


class _Incompatible(Exception):
    """The device advertises our service but does not implement the contract."""


BLE_SERVICE = BleService()
