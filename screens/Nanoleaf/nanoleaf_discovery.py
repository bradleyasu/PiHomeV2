"""mDNS discovery for Nanoleaf controllers on the local network.

Uses the ``zeroconf`` library to scan for ``_nanoleafapi._tcp.local.``
services.  Falls back gracefully if zeroconf is not installed.
"""

import socket
import threading

from util.phlog import PIHOME_LOGGER

_SERVICE_TYPE = "_nanoleafapi._tcp.local."
_SCAN_TIMEOUT = 6  # seconds to scan before stopping

try:
    from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
    _ZEROCONF_AVAILABLE = True
except ImportError:
    _ZEROCONF_AVAILABLE = False


# Model ID → friendly name mapping (common Nanoleaf products)
_MODEL_NAMES = {
    "NL22": "Shapes Triangle",
    "NL42": "Shapes Mini Triangle",
    "NL47": "Shapes Hexagon",
    "NL29": "Canvas",
    "NL52": "Elements Hexagon",
    "NL59": "Lines",
    "NL69": "4D Lightstrip",
}


class NanoleafDiscovery:
    """Scan the local network for Nanoleaf controllers via mDNS.

    Usage::

        def on_found(device):
            # device = {"name": ..., "ip": ..., "port": ..., "model": ..., "device_id": ...}
            print(f"Found: {device}")

        discovery = NanoleafDiscovery(on_found=on_found)
        discovery.start()
        # ... wait ...
        discovery.stop()
    """

    def __init__(self, on_found=None, on_complete=None):
        self._on_found = on_found
        self._on_complete = on_complete
        self._zc = None
        self._browser = None
        self._thread = None
        self._found = {}  # keyed by IP to deduplicate

    @staticmethod
    def is_available():
        return _ZEROCONF_AVAILABLE

    def start(self):
        """Begin scanning in a background thread."""
        if not _ZEROCONF_AVAILABLE:
            PIHOME_LOGGER.warn("Nanoleaf: zeroconf not installed — run: pip install zeroconf")
            if self._on_complete:
                self._on_complete([])
            return

        self._found.clear()
        self._thread = threading.Thread(
            target=self._scan, daemon=True, name="nanoleaf-mdns",
        )
        self._thread.start()

    def stop(self):
        """Stop scanning and clean up."""
        if self._browser:
            self._browser.cancel()
            self._browser = None
        if self._zc:
            self._zc.close()
            self._zc = None

    def _scan(self):
        try:
            self._zc = Zeroconf()
            self._browser = ServiceBrowser(
                self._zc, _SERVICE_TYPE, handlers=[self._on_state_change],
            )

            # Let the browser collect services for the scan duration
            threading.Event().wait(_SCAN_TIMEOUT)

        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf: mDNS scan error: {e}")
        finally:
            self.stop()
            if self._on_complete:
                self._on_complete(list(self._found.values()))

    def _on_state_change(self, zeroconf, service_type, name, state_change):
        if state_change != ServiceStateChange.Added:
            return

        try:
            info = zeroconf.get_service_info(service_type, name)
            if info is None:
                return

            # Extract IP address
            ip = None
            if info.addresses:
                ip = socket.inet_ntoa(info.addresses[0])
            if not ip:
                return

            # Extract TXT record properties
            props = {}
            if info.properties:
                for k, v in info.properties.items():
                    key = k.decode("utf-8") if isinstance(k, bytes) else k
                    val = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                    props[key] = val

            model_id = props.get("md", "")
            device_id = props.get("id", "")
            friendly_model = _MODEL_NAMES.get(model_id, model_id)

            # Build a friendly display name from the service name
            # Service name format: "XX:XX:XX:XX:XX:XX" or device name
            display_name = name.replace(f".{_SERVICE_TYPE}", "").strip()
            if display_name and len(display_name) > 20:
                display_name = display_name[:20]

            device = {
                "name": display_name,
                "ip": ip,
                "port": info.port or 16021,
                "model": friendly_model,
                "model_id": model_id,
                "device_id": device_id,
            }

            if ip not in self._found:
                self._found[ip] = device
                PIHOME_LOGGER.info(f"Nanoleaf: discovered {display_name} at {ip} ({friendly_model})")
                if self._on_found:
                    self._on_found(device)

        except Exception as e:
            PIHOME_LOGGER.error(f"Nanoleaf: mDNS service parse error: {e}")
