import os
import platform
import subprocess
import time

_BOOT_TIME = None


def get_cpu_temp():
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"], stdout=subprocess.PIPE, timeout=3
        )
        return result.stdout.decode("utf-8").replace("temp=", "").replace("'C\n", "").strip()
    except Exception:
        return "N/A"


def get_memory_usage():
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        info = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                info[parts[0].strip()] = int(parts[1].strip().split()[0])
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", 0)
        used = total - available
        total_mb = total // 1024
        used_mb = used // 1024
        pct = round((used / total) * 100) if total > 0 else 0
        return {"total_mb": total_mb, "used_mb": used_mb, "percent": pct}
    except Exception:
        return {"total_mb": 0, "used_mb": 0, "percent": 0}


def get_disk_usage():
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        total_gb = round(total / (1024 ** 3), 1)
        used_gb = round(used / (1024 ** 3), 1)
        pct = round((used / total) * 100) if total > 0 else 0
        return {"total_gb": total_gb, "used_gb": used_gb, "percent": pct}
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "percent": 0}


def get_uptime():
    global _BOOT_TIME
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
        if _BOOT_TIME is None:
            _BOOT_TIME = time.time() - uptime_seconds
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        if days > 0:
            return "{}d {}h {}m".format(days, hours, minutes)
        elif hours > 0:
            return "{}h {}m".format(hours, minutes)
        else:
            return "{}m".format(minutes)
    except Exception:
        return "N/A"


def get_hostname():
    return platform.node() or "unknown"


def get_python_version():
    return platform.python_version()


def get_os_info():
    try:
        with open("/etc/os-release", "r") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "{} {}".format(platform.system(), platform.release())


def get_architecture():
    return platform.machine()


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"
