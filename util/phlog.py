import logging

from util.helpers import get_config

class phlog:
    levels = {
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'WARN': logging.WARNING,
        'ERROR': logging.ERROR
    }
    def __init__(self):
        self.level = get_config().get('logging', 'level', 'INFO')
        self.output = get_config().get('logging', 'out', 'pihome.log')
        # self.logger = logging.basicConfig(format='%(asctime)s : [ %(levelname)s ] : %(message)s', filename=self.output, level=self.levels[self.level])
        self.logger = logging.getLogger('pihome_default')
        self.logger.setLevel(self.levels[self.level])
        handler = logging.FileHandler(self.output)
        formatter = logging.Formatter('%(asctime)s : [ %(levelname)s ] : %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.info('---------------PIHOME LOGGER STARTED---------------')


    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warn(self, message):
        self.logger.warn(message)

    def error(self, message):
        self.logger.error(message)