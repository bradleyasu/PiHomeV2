from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label
from components.Button.circlebutton import CircleButton
from theme.color import Color
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp, sp
from util.helpers import get_app
from util.tools import hex
from kivy.uix.widget import Widget
from kivy.clock import Clock

Builder.load_file("./composites/BusEta/buseta.kv")

class BusEta(Widget):
    theme = Theme()
    route        = StringProperty()
    dest         = StringProperty()
    dest_loc     = StringProperty()
    eta          = StringProperty()
    stop         = StringProperty()

    # Always-white text on the colored route badge
    route_background_color = ColorProperty(theme.get_color(theme.ALERT_INFO))

    # ETA colors — 3-tier urgency
    time_color   = ColorProperty(theme.get_color(theme.ALERT_SUCCESS))
    danger_color = ColorProperty(theme.get_color(theme.ALERT_DANGER))
    amber_color  = ColorProperty(theme.get_color(theme.ALERT_WARNING))

    # Split ETA display
    eta_value    = StringProperty("--")
    eta_unit     = StringProperty("min")
    eta_font_size = StringProperty("28sp")

    # Theme-aware card surfaces
    card_bg_color     = ColorProperty([1.0, 1.0, 1.0, 0.07])
    card_border_color = ColorProperty([1.0, 1.0, 1.0, 0.04])
    text_color        = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))

    blinkOpacity = NumericProperty(1)

    def _apply_theme(self):
        """Card tint from text_color (low alpha, inverts per mode); border from
        the border token."""
        t = Theme()
        self.text_color = t.get_color(t.TEXT_PRIMARY)
        tc = self.text_color
        self.card_bg_color     = [tc[0], tc[1], tc[2], 0.06]
        self.card_border_color = list(t.get_color(t.BACKGROUND_BORDER))

    def on_config_update(self, config=None):
        self._apply_theme()

    def __init__(self, stop="--", route="--", dest="BOUND", dest_loc="", eta="Unknown", **kwargs):
        super(BusEta, self).__init__(**kwargs)

        # Refresh text_color and card surfaces for current theme mode
        self._apply_theme()

        self.size = (dp(get_app().width - 32), dp(72))
        self.route    = route
        self.stop     = stop
        self.dest     = dest
        self.dest_loc = dest_loc
        self.eta      = eta

        # Split eta string into display value + unit, and pick urgency color
        if eta == "Now Arriving":
            self.eta_value     = "NOW"
            self.eta_unit      = ""
            self.eta_font_size = "18sp"
            self.time_color    = self.danger_color
        else:
            try:
                mins = int(eta.split(" ")[0])
                self.eta_value = str(mins)
                self.eta_unit  = "min"
                self.eta_font_size = "28sp"
                if mins < 5:
                    self.time_color = self.danger_color
                elif mins < 10:
                    self.time_color = self.amber_color
                # else: keeps default success/green
            except (ValueError, IndexError):
                self.eta_value = eta
                self.eta_unit  = ""
                self.eta_font_size = "14sp"
