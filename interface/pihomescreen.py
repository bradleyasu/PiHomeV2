from kivy.uix.screenmanager import Screen

from util.helpers import goto_screen

class PiHomeScreen(Screen):

    def __init__(self, icon = "https://seeklogo.com/images/R/raspberry-pi-logo-8240ABBDFE-seeklogo.com.png", label = "PiHome App", is_hidden = False, requires_pin = False, **kwargs):
        super(PiHomeScreen, self).__init__(**kwargs)
        self.icon = icon
        self.label = label
        self.is_hidden = is_hidden 
        self.requires_pin = requires_pin
