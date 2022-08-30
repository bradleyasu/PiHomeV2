import os
import platform
import subprocess

from util.helpers import info, warn
'''
Set the brightness of the display(s) on a 0-100% scale

Example System Command: 
sudo sh -c 'echo 255 > /sys/class/backlight/%k/brightness'
'''
def set_brightness(percent_level):
    # Convert brightness percent to value
    level = round((percent_level / 100) * 255)
    if platform.system() == 'Darwin':
        warn("set brightness to {} is ignored while running on unsupported OS".format(level))
        return
    for hardware in os.listdir('/sys/class/backlight'):
        args = [
            'sudo',
            'sh',
            '-c',
            'echo {} > /sys/class/backlight/{}/brightness'.format(level, hardware)
        ]
        info("Hardware: {} brightness set to {}".format(hardware, level))
        subprocess.call(args)
