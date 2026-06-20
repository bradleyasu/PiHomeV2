import os
import platform
import subprocess

from util.phlog import PIHOME_LOGGER
'''
Enable/disable the Raspberry Pi onboard LEDs (green ACT, red PWR) that shine
through the PiHome enclosure.

Each LED is a directory under /sys/class/leds:
 - Pi 3/4: led0 = ACT (green), led1 = PWR (red)
 - Pi 5:   ACT, PWR
So we enumerate the directory rather than hardcode names.

Example System Command:
sudo sh -c 'echo none > /sys/class/leds/led0/trigger; echo 0 > /sys/class/leds/led0/brightness'
'''

LED_DIR = "/sys/class/leds"


def _default_trigger(name):
    n = name.lower()
    if "pwr" in n or n == "led1":
        return "default-on"     # red PWR LED
    return "mmc0"               # green ACT LED (led0 / ACT)


def set_leds(enabled):
    """enabled=True -> normal/on, False -> off."""
    if platform.system() == 'Darwin':
        PIHOME_LOGGER.warn("set_leds({}) ignored while running on unsupported OS".format(enabled))
        return
    if not os.path.isdir(LED_DIR):
        return
    for name in os.listdir(LED_DIR):
        path = "{}/{}".format(LED_DIR, name)
        if enabled:
            cmd = "echo {0} > {1}/trigger".format(_default_trigger(name), path)
        else:
            cmd = "echo none > {0}/trigger; echo 0 > {0}/brightness".format(path)
        subprocess.call(["sudo", "sh", "-c", cmd])
        PIHOME_LOGGER.info("LED {} -> {}".format(name, "on" if enabled else "off"))
