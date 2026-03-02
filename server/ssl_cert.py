"""Self-signed SSL certificate management for PiHome's HTTP server.

Generates a cert on first run that covers:
  - localhost / 127.0.0.1
  - the machine's detected LAN IP (e.g. 192.168.x.x)
  - the hostname (e.g. pihome.local)

This lets Spotify (and other OAuth providers) accept https:// redirect URIs
pointing at the Pi's LAN address.  Mobile browsers will show a one-time
"untrusted certificate" warning on first visit — tap Advanced → Proceed.

The cert and key are stored in TEMP_DIR and regenerated whenever the
detected LAN IP changes (i.e. after a DHCP reassignment).
"""

import os
import socket
import ssl
import subprocess
import tempfile

from util.const import TEMP_DIR
from util.phlog import PIHOME_LOGGER

_CERT_FILE = os.path.join(TEMP_DIR, "pihome-tls.crt")
_KEY_FILE  = os.path.join(TEMP_DIR, "pihome-tls.key")
_IP_FILE   = os.path.join(TEMP_DIR, "pihome-tls.ip")   # stores IP the cert was issued for


def _local_lan_ip() -> str:
    """Return the machine's primary LAN IP (not loopback)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _cert_is_current(lan_ip: str) -> bool:
    """True if a cert exists and was generated for the current LAN IP."""
    if not (os.path.exists(_CERT_FILE) and os.path.exists(_KEY_FILE)):
        return False
    try:
        stored = open(_IP_FILE).read().strip()
        return stored == lan_ip
    except OSError:
        return False


def _generate(lan_ip: str) -> bool:
    """Generate a new self-signed cert via openssl subprocess. Returns True on success."""
    hostname = socket.gethostname()
    os.makedirs(TEMP_DIR, exist_ok=True)

    # Write an openssl config that includes proper SAN fields.
    # Modern browsers ignore CN and require SAN for HTTPS.
    cfg = f"""[req]
distinguished_name = req_dn
x509_extensions   = v3_req
prompt            = no

[req_dn]
CN = PiHome

[v3_req]
subjectAltName      = @alt_names
keyUsage            = critical, digitalSignature, keyEncipherment
extendedKeyUsage    = serverAuth
basicConstraints    = critical, CA:FALSE

[alt_names]
DNS.1 = localhost
DNS.2 = {hostname}
IP.1  = 127.0.0.1
IP.2  = {lan_ip}
"""
    cfg_path = os.path.join(TEMP_DIR, "pihome-tls.cnf")
    with open(cfg_path, "w") as f:
        f.write(cfg)

    try:
        subprocess.run(
            [
                "openssl", "req",
                "-x509",
                "-newkey", "rsa:2048",
                "-keyout", _KEY_FILE,
                "-out",    _CERT_FILE,
                "-days",   "3650",
                "-nodes",
                "-config", cfg_path,
            ],
            check=True,
            capture_output=True,
        )
        with open(_IP_FILE, "w") as f:
            f.write(lan_ip)
        PIHOME_LOGGER.info(
            f"SSL: generated self-signed cert for {lan_ip} / {hostname}"
        )
        return True
    except FileNotFoundError:
        PIHOME_LOGGER.error(
            "SSL: openssl not found — install it with: sudo apt install openssl"
        )
        return False
    except subprocess.CalledProcessError as e:
        PIHOME_LOGGER.error(f"SSL: openssl failed: {e.stderr.decode()}")
        return False
    finally:
        try:
            os.remove(cfg_path)
        except OSError:
            pass


def make_ssl_context() -> ssl.SSLContext | None:
    """Return a configured SSLContext, generating a cert first if needed.

    Returns None if SSL setup fails (server falls back to plain HTTP).
    """
    lan_ip = _local_lan_ip()

    if not _cert_is_current(lan_ip):
        PIHOME_LOGGER.info(f"SSL: (re)generating certificate for LAN IP {lan_ip}")
        if not _generate(lan_ip):
            return None

    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(_CERT_FILE, _KEY_FILE)
        return ctx
    except Exception as e:
        PIHOME_LOGGER.error(f"SSL: failed to load certificate: {e}")
        return None


def lan_ip() -> str:
    """Expose the detected LAN IP so other modules (e.g. SpotifyScreen) can use it."""
    return _local_lan_ip()
