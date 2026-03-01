from datetime import datetime as dt
import math
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty
from kivy.graphics import Color, Rectangle, Line

from kivy.uix.scrollview import ScrollView

from components.Empty.empty import Empty
from components.Switch.switch import PiHomeSwitch
from composites.BusEta.buseta import BusEta
from interface.pihomescreen import PiHomeScreen
from networking.poller import POLLER
from theme.theme import Theme
from util.configuration import CONFIG
from util.helpers import get_app
from kivy.clock import Clock

Builder.load_file("./screens/Bus/bus.kv")

class BusScreen(PiHomeScreen):
    """
    Bus Screen Dedicated to PortAuthority Service in Pittsburgh Area.  Can be used as a tempalte
    for pulling Bus Service information from other open API's.
    """
    api_url = ""
    theme = Theme()
    color = ColorProperty()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    image = StringProperty()
    outbound = False
    
    pending_updates = False
    data = None
    scroller = None

    PRT_API = "https://realtime.portauthority.org/bustime/api/v3/getpredictions?rtpidatafeed=Port Authority Bus&key={}&format=json&rt={}&stpid={}"

    def __init__(self, **kwargs):
        super(BusScreen, self).__init__(**kwargs)
        self.api_key = CONFIG.get('prt', 'api_key', '')
        self.routes = CONFIG.get('prt', 'routes', '')
        self.stops =  CONFIG.get('prt', 'stops', '')
        self.logo= CONFIG.get('prt', 'logo', '')
        
        self.api = self.PRT_API.format(self.api_key, self.routes, self.stops)
        
        # Register API to be polled every 200 seconds
        POLLER.register_api(self.api, 60, lambda json: self.update(json))
        Clock.schedule_interval(self._update, 1)

        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY, 0.8)
        self.build()

    def build(self):
        t = Theme()
        bg_color  = t.get_color(t.BACKGROUND_SECONDARY)
        div_color = list(t.get_color(t.TEXT_PRIMARY))
        div_color[3] = 0.10

        outer = FloatLayout()

        # ── Header bar ────────────────────────────────────────────────
        header = BoxLayout(
            orientation='horizontal',
            size_hint=(None, None),
            size=(dp(get_app().width), dp(68)),
            pos=(0, dp(get_app().height - 68)),
            padding=(dp(72), dp(8), dp(16), dp(8)),
            spacing=dp(12),
        )

        with header.canvas.before:
            _bg_color  = Color(*bg_color)
            _bg_rect   = Rectangle(size=header.size, pos=header.pos)
            _div_color = Color(*div_color)
            _div_line  = Line(
                points=[0, dp(get_app().height - 68),
                        dp(get_app().width), dp(get_app().height - 68)],
                width=dp(1)
            )

        def _sync_header(*args):
            _bg_rect.size = header.size
            _bg_rect.pos  = header.pos
            _div_line.points = [
                header.x, header.y,
                header.right, header.y,
            ]
        header.bind(size=_sync_header, pos=_sync_header)

        # Left: title + live stop name
        left_col = BoxLayout(orientation='vertical', spacing=dp(1))
        title_lbl = Label(
            text="Bus Arrivals",
            font_size="18sp",
            bold=True,
            color=t.get_color(t.TEXT_PRIMARY),
            size_hint_y=None, height=dp(30),
            halign='left', valign='middle',
        )
        title_lbl.bind(size=lambda w, s: setattr(w, 'text_size', (s[0], None)))

        stop_color = list(t.get_color(t.TEXT_PRIMARY))
        stop_color[3] = 0.55
        self.stop_lbl = Label(
            text="",
            font_size="11sp",
            color=stop_color,
            size_hint_y=None, height=dp(20),
            halign='left', valign='middle',
        )
        self.stop_lbl.bind(size=lambda w, s: setattr(w, 'text_size', (s[0], None)))
        left_col.add_widget(title_lbl)
        left_col.add_widget(self.stop_lbl)
        header.add_widget(left_col)

        # Right: bound label + toggle switch
        right_col = BoxLayout(
            orientation='horizontal',
            size_hint=(None, None),
            size=(dp(180), dp(52)),
            spacing=dp(8),
            pos_hint={'center_y': 0.5},
        )
        self.bound_label = Label(
            text="INBOUND",
            font_size="13sp",
            color=t.get_color(t.TEXT_PRIMARY),
            size_hint_x=None, width=dp(76),
            halign='right', valign='middle',
        )
        self.bound_label.bind(size=lambda w, s: setattr(w, 'text_size', s))
        s = PiHomeSwitch(size=(dp(96), dp(36)), size_hint=(None, None), pos_hint={'center_y': 0.5})
        s.bind(enabled=lambda x, y: self.set_outbound(y))
        right_col.add_widget(self.bound_label)
        right_col.add_widget(s)
        header.add_widget(right_col)

        outer.add_widget(header)

        # ── Empty state ───────────────────────────────────────────────
        self.empty_state = Empty(
            message="There are no busses coming anytime soon",
            size=(dp(get_app().width), dp(get_app().height - 68)),
        )
        self.empty_state.opacity = 0
        self.add_widget(self.empty_state)

        # ── Scroll + grid ─────────────────────────────────────────────
        self.grid = GridLayout(
            cols=1,
            spacing=dp(8),
            size_hint_y=None,
            padding=(dp(16), dp(8), dp(16), dp(16)),
        )
        self.grid.bind(minimum_height=self.grid.setter('height'))

        scroll_h = dp(get_app().height - 68)
        view = ScrollView(
            size_hint=(None, None),
            size=(dp(get_app().width), scroll_h),
            pos=(0, 0),
        )
        view.add_widget(self.grid)
        outer.add_widget(view)
        self.scroller = view

        self.add_widget(outer)


    def scroll_y(self, amount):
        # 1 is top and 0 is bottom of scroll view
        # convert scroll view to a tenth of a percent

        if self.scroller.scroll_y + amount > 1:
            return
        if self.scroller.scroll_y + amount < 0:
            return
        self.scroller.scroll_to(self.scroller, 0, self.scroller.scroll_y + amount, True)

    def on_rotary_turn(self, direction, pressed):
        if direction == 1:
            self.scroll_y(0.1)
        elif direction == -1:
            self.scroll_y(-0.1)

    def on_rotary_pressed(self):
        self.set_outbound(not self.outbound)

    def set_outbound(self, enabled):
        if enabled:
            self.bound_label.text = "OUTBOUND"
        else:
            self.bound_label.text = "INBOUND"
        self.outbound = enabled
        self.pending_updates = True

    def update(self, payload):
        self.data = payload['bustime-response']
        self.pending_updates = True


    def _update(self, param): 
        if self.pending_updates: 
            self.pending_updates = False
            self.grid.clear_widgets()
            self.stop_lbl.text = ""   # reset; gets filled from first prediction
            no_data = True
            if "prd" in self.data:
                arr = self.data['prd']
                for i in arr:
                    if "prdtm" in i:
                        no_data = False
                        r = i["rt"]
                        s = i["stpnm"]
                        d = i['rtdir']
                        dloc = i['des']
                        e = i['prdtm']
                        dts = dt.now()
                        dte = dt.strptime(e, '%Y%m%d %H:%M')
                        est = math.floor((dte - dts).total_seconds() / 60.0)

                        label="{} min".format(est)
                    
                        if est < 1:
                            label = "Now Arriving"

                        # Update live stop name in header from first arrival
                        if self.stop_lbl.text == "":
                            self.stop_lbl.text = s

                        b = BusEta(route=r, stop=s, dest=d, dest_loc=dloc, eta=label)
                        if self.outbound and d == "OUTBOUND":
                            self.grid.add_widget(b)
                        elif not self.outbound and d == "INBOUND":
                            self.grid.add_widget(b)

            if no_data == True:
                self.empty_state.opacity = 1
            else:
                self.empty_state.opacity = 0