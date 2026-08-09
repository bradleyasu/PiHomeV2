"""Standalone BLE connect probe -- run this ON THE PI, with PiHome STOPPED.

It uses only bleak, so if it fails the problem is BlueZ or the device, and
nothing in PiHome can fix it. If it succeeds, the problem is PiHome's logic.

    sudo systemctl stop pihome
    python3 screens/BluetoothConnect/tests/ble_probe.py AA:BB:CC:DD:EE:FF

Add --loop to repeat, which is how you reproduce a reconnect failure:
connect, drop, reconnect, over and over.
"""

import asyncio
import sys
import time

from bleak import BleakClient, BleakScanner

TX_UUID = "eb96a621-c93b-4cca-b6c3-d79215350f65"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def attempt(address, settle):
    log(f"scanning for {address} ...")
    t0 = time.time()
    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    log(f"  scan returned {device!r} after {time.time() - t0:.1f}s")

    if settle:
        log(f"  waiting {settle}s for discovery to wind down")
        await asyncio.sleep(settle)

    log("connecting ...")
    t0 = time.time()
    client = BleakClient(device or address, timeout=20.0)
    try:
        await client.connect()
        log(f"  CONNECTED in {time.time() - t0:.1f}s")
        names = [c.uuid for s in client.services for c in s.characteristics]
        log(f"  characteristics: {len(names)}")
        log(f"  PiHome TX present: {TX_UUID in [n.lower() for n in names]}")

        got = []
        await client.start_notify(TX_UUID, lambda s, d: got.append(bytes(d)))
        log("  subscribed, listening 10s ...")
        await asyncio.sleep(10)
        log(f"  received {len(got)} notification(s): {got[:5]}")
        return True
    except Exception as e:
        log(f"  FAILED after {time.time() - t0:.1f}s -> {e.__class__.__name__}: {e}")
        return False
    finally:
        try:
            await client.disconnect()
            log("  disconnected")
        except Exception as e:
            log(f"  disconnect raised: {e}")


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return
    address = args[0]
    loop_mode = "--loop" in sys.argv
    settle = 1.0 if "--no-settle" not in sys.argv else 0

    run = 0
    while True:
        run += 1
        log(f"===== attempt {run} =====")
        ok = await attempt(address, settle)
        if not loop_mode:
            log("done" if ok else "done (failed)")
            return
        log("sleeping 5s before the next attempt")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
