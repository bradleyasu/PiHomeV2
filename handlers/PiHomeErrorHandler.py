from kivy.base import ExceptionManager, ExceptionHandler


class PiHomeErrorHandler(ExceptionHandler):
    def handle_exception(self, inst):
        print(inst)
        return ExceptionManager.PASS

