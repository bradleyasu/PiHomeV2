from kivy.base import ExceptionManager, ExceptionHandler

from util.phlog import PIHOME_LOGGER


class PiHomeErrorHandler(ExceptionHandler):
    def handle_exception(self, inst):
        # Don't catch KeyboardInterrupt or SystemExit - let them propagate
        if isinstance(inst, (KeyboardInterrupt, SystemExit)):
            return ExceptionManager.RAISE
        
        print(inst)
        try:
            PIHOME_LOGGER.error(f"An error occurred: {type(inst).__name__}: {str(inst)}")
        except Exception as e:
            # If logging fails, at least print it
            print(f"Error handler failed: {e}")
        return ExceptionManager.PASS

