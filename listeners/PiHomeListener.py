
class PiHomeListener:
    type = "pihome"

    def __init__(self):
        pass

    def callback(self, payload):
        print(payload)
