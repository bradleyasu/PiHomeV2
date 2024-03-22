import logging
from util.configuration import CONFIG


class phlog:
    levels = {
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'WARN': logging.WARNING,
        'ERROR': logging.ERROR
    }
    def __init__(self):
        self.level = CONFIG.get('logging', 'level', 'INFO')
        self.output = CONFIG.get('logging', 'out', 'pihome.log')
        self.clear_log()
        # self.logger = logging.basicConfig(format='%(asctime)s : [ %(levelname)s ] : %(message)s', filename=self.output, level=self.levels[self.level])
        self.logger = logging.getLogger('pihome_default')
        self.logger.setLevel(self.levels[self.level])
        handler = logging.FileHandler(self.output)
        formatter = logging.Formatter('%(asctime)s : [ %(levelname)s ] : %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.info('---------------PIHOME LOGGER STARTED---------------')


    def clear_log(self):
        with open(self.output, 'w') as f:
            f.write('')


    def is_raspberry_pi(self):
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Hardware'):
                        return True
        except:
            return False


    def debug(self, message):
        self.logger.debug(message)
        if self.is_raspberry_pi():
            return
        # print debug messages in blue color
        print("\033[94mDEBUG: ", message, "\033[0m")

    def info(self, message):
        self.logger.info(message)
        if self.is_raspberry_pi():
            return
        # print info messages in green color
        print("\033[92mINFO: ", message, "\033[0m")

    def warn(self, message):
        self.logger.warn(message)
        if self.is_raspberry_pi():
            return
        # print warnings in orange color
        print("\033[93mWARN: ", message, "\033[0m")

    def warning(self, message):
        self.warn(message)

    def error(self, message):
        self.logger.error(message)
        if self.is_raspberry_pi():
            return
        # print errors in red color 
        print("\033[91mERROR: ", message, "\033[0m")

PIHOME_LOGGER = phlog()