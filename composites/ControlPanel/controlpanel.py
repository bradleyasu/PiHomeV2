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


# Lazy proxy to avoid Window initialization during import
_REAL_CONTROL_PANEL = None

class _ControlPanelProxy:
    """Proxy that creates the real control panel on first access"""
    
    def _get_real_panel(self):
        global _REAL_CONTROL_PANEL
        if _REAL_CONTROL_PANEL is None:
            _REAL_CONTROL_PANEL = ControlPanel()
        return _REAL_CONTROL_PANEL
    
    def __getattr__(self, name):
        return getattr(self._get_real_panel(), name)
    
    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            setattr(self._get_real_panel(), name, value)
    
    @property
    def __class__(self):
        if _REAL_CONTROL_PANEL is not None:
            return _REAL_CONTROL_PANEL.__class__
        return ControlPanel
    
    def __bool__(self):
        return True
    
    def __repr__(self):
        if _REAL_CONTROL_PANEL is None:
            return "<ControlPanel (not yet initialized)>"
        return repr(_REAL_CONTROL_PANEL)

CONTROL_PANEL = _ControlPanelProxy()