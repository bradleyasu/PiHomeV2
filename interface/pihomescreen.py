from kivy.uix.screenmanager import Screen

from util.helpers import goto_screen

class PiHomeScreen(Screen):
    def __init__(self, **kwargs):
        super(PiHomeScreen, self).__init__(**kwargs)
        self.icon = ""

    def goto(self, screen, protected = False):
        goto_screen(screen, protected)
