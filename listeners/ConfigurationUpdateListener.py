from listeners.PiHomeListener import PiHomeListener

class ConfigurationUpdateListener(PiHomeListener):

    def __init__(self, callback):
        self.callback = callback
        self.type = "configuration_update"