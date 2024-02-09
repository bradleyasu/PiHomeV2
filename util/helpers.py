import subprocess
import socket
import uuid
import math
from kivy.app import App
from kivy.clock import Clock
from kivy.gesture import Gesture


def get_app():
    return App.get_running_app()

def get_config():
    return get_app().get_config()

def get_poller():
    return get_app().get_poller()

def goto_screen(screen):
    get_app().goto_screen(screen, True)


def appmenu_open(open = True):
    get_app().set_app_menu_open(open)

def toast(label, level = "info", timeout = 5):
    get_app().show_toast(label = label, level = level, timeout = timeout);

def process_webhook(webhook):
    if get_app().mqtt is not None:
        get_app().mqtt.process_webhook(webhook)
    else:
        warn("No MQTT service available to process webhook")

def weather():
    return get_app().weather


def update_pihome():
    """
    Notify user of update, pull latest, and restart
    """
    get_app().server.stop_server()
    toast("PiHome updates are available. PiHome will restart in less than 30 seconds", level = "warn", timeout = 30)
    Clock.schedule_once(lambda _: subprocess.call(['sh', './update_and_restart.sh']), 32)


def audio_player():
    return get_app().audio_player


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



'''
    Logging helpers
'''
def debug(message):
    get_app().phlogger.debug(message)

def info(message):
    get_app().phlogger.info(message)

def warn(message):
    print(message)
    get_app().phlogger.warn(message)
    
def error(message):
    get_app().phlogger.error(message)


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
