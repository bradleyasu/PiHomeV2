from kivy.base import ExceptionManager, ExceptionHandler

from util.phlog import PIHOME_LOGGER


class PiHomeErrorHandler(ExceptionHandler):
    def handle_exception(self, inst):
        print(inst)
        try:
            PIHOME_LOGGER.error("An error occurred: " + str(inst))
        except:
            pass
        return ExceptionManager.PASS

