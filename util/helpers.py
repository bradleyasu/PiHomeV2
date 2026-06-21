import subprocess
import socket
import uuid
import math
from kivy.app import App
from kivy.clock import Clock
from kivy.gesture import Gesture

from util.phlog import PIHOME_LOGGER
# from server.server import SERVER

# from composites.TimerDrawer.timerdrawer import TIMER_DRAWER

def get_app():
    return App.get_running_app()


def appmenu_open(open = True):
    get_app().set_app_menu_open(open)

def toast(label, level = "info", timeout = 5):
    get_app().show_toast(label = label, level = level, timeout = timeout);

def process_webhook(webhook):
    if get_app().mqtt is not None:
        get_app().mqtt.process_webhook(webhook)
    else:
        PIHOME_LOGGER.warn("No MQTT service available to process webhook")


def update_pihome():
    """
    Notify user of update, pull latest, and restart
    """
    # SERVER.stop_server()
    toast("PiHome updates are available. PiHome will restart in less than 5 seconds", level = "warn", timeout = 5)
    # TIMER_DRAWER.create_timer(30, "Restarting PiHome")
    Clock.schedule_once(lambda _: subprocess.call(['sh', './update_and_restart.sh']), 5)


def simplegesture(name, point_list):
    g = Gesture()
    g.add_stroke(point_list)
    g.normalize()
    g.name = name
    return g


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    LOCAL_IP = s.getsockname()[0]
    s.close()
    return LOCAL_IP


def random_hash():
    return uuid.uuid4().hex



'''
    math helpers
'''

def calculate_angle(x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    angle_radians = math.atan2(dy, dx)
    angle_degrees = math.degrees(angle_radians)
    angle_degrees = (angle_degrees - 90 + 360) % 360
    return 360 - angle_degrees

def select_item_by_degree(arr, degree):
    if not 0 <= degree <= 360:
        raise ValueError("Degree value must be between 0 and 360 (inclusive)")

    section_size = 360 / len(arr)
    section_index = int(degree // section_size)

    selected_item = arr[section_index]
    return selected_item, section_index


# This function generates a uniq hash for the url provided.  If the same url is entered, the same hash will be output
def url_hash(url):
    return uuid.uuid5(uuid.NAMESPACE_URL, url).hex


# Keep below the Raspberry Pi GPU's GL_MAX_TEXTURE_SIZE (commonly 2048 on older
# Pis).  Images larger than this fail to upload to a texture and render blank.
MAX_DISPLAY_EDGE = 2048


def prepare_display_image(src):
    """Resolve and size-limit an image source so an event screen can display it.

    Single entry point for every image-capable event (Image/Display/Task).  It:
      * resolves PiHome upload URLs to their local file (via UPLOADS), and
      * fixes EXIF orientation and/or downscales any image whose longest edge
        exceeds MAX_DISPLAY_EDGE — which would otherwise blow past the Pi's GPU
        texture limit and render blank — caching the result in TEMP_DIR.

    Small, correctly-oriented images are returned untouched: a local upload as
    its file path, an external URL as the original URL so Kivy's AsyncImage keeps
    loading/reloading it asynchronously.  Only oversized/rotated sources get
    localized into a cached copy.

    Runs synchronously (a brief block is acceptable for these user-triggered
    events).  Returns a path/URL ready for AsyncImage; on any failure returns the
    best-effort resolved source so loading still falls back gracefully.
    """
    if not src or not isinstance(src, str):
        return src

    from services.uploads.uploads import UPLOADS
    try:
        resolved = UPLOADS.resolve_url(src)
    except Exception:
        resolved = src

    try:
        import os
        from io import BytesIO
        import requests
        from PIL import Image as PILImage, ImageOps
        from util.const import TEMP_DIR

        # Never reprocess animated GIFs — resizing would flatten them to a frame.
        if resolved.lower().split("?")[0].endswith(".gif"):
            return resolved

        cache_path = os.path.join(TEMP_DIR, "_disp_{}.png".format(url_hash(src)))
        if os.path.exists(cache_path):
            return cache_path

        is_local = os.path.isfile(resolved)
        if is_local:
            img = PILImage.open(resolved)
        elif resolved.startswith("http://") or resolved.startswith("https://"):
            r = requests.get(resolved, timeout=15)
            content = r.content
            r.close()
            img = PILImage.open(BytesIO(content))
        else:
            return resolved  # unknown scheme; let AsyncImage try it

        needs_orient = img.getexif().get(0x0112, 1) not in (0, 1)
        oversize = max(img.size) > MAX_DISPLAY_EDGE
        if not needs_orient and not oversize:
            img.close()
            # Nothing to fix: use the local file directly, or hand the external
            # URL back so AsyncImage loads (and can reload) it natively.
            return resolved if is_local else src

        img = ImageOps.exif_transpose(img)
        if max(img.size) > MAX_DISPLAY_EDGE:
            img = ImageOps.contain(img, (MAX_DISPLAY_EDGE, MAX_DISPLAY_EDGE))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        os.makedirs(TEMP_DIR, exist_ok=True)
        img.save(cache_path, format="png")
        img.close()
        PIHOME_LOGGER.info("prepare_display_image: cached display copy for {} -> {}".format(src, cache_path))
        return cache_path
    except Exception as e:
        PIHOME_LOGGER.error("prepare_display_image: failed for {}: {}".format(src, e))
        return resolved
