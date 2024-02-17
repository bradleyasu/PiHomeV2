from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.properties import StringProperty
from services.timers.timer import Timer
from kivy.clock import Clock
import time
from components.Msgbox.msgbox import MSGBOX_FACTORY
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView

Builder.load_file("./composites/ControlPanel/controlpanel.kv")

class ControlPanel(ModalView):

    def __init__(self, **kwargs):
        super(ControlPanel, self).__init__(**kwargs)
        self.size = (dp(300), dp(300))


CONTROL_PANEL = ControlPanel()