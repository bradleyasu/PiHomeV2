import subprocess
import socket
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
    get_app().phlogger.warn(message)
    
def error(message):
    get_app().phlogger.error(message)