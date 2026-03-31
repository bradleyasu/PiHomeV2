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
    _poller_key = None

    PRT_API = "https://realtime.portauthority.org/bustime/api/v3/getpredictions?rtpidatafeed=Port Authority Bus&key={}&format=json&rt={}&stpid={}"

    def __init__(self, **kwargs):
        super(BusScreen, self).__init__(**kwargs)
        self.api_key = CONFIG.get('prt', 'api_key', '')
        self.routes = CONFIG.get('prt', 'routes', '')
        self.stops =  CONFIG.get('prt', 'stops', '')
        
        self.api = self.PRT_API.format(self.api_key, self.routes, self.stops)
        self._update_event = None

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
        left_col = BoxLayout(orientation='vertical', spacing=dp(1), size_hint_x=1)
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
            size=(dp(136), dp(52)),
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
        s = PiHomeSwitch(size=(dp(50), dp(28)), size_hint=(None, None), pos_hint={'center_y': 0.5})
        s.bind(enabled=lambda x, y: self.set_outbound(y))
        right_col.add_widget(self.bound_label)
        right_col.add_widget(s)
        header.add_widget(right_col)

        outer.add_widget(header)

        # ── Empty state ───────────────────────────────────────────────
        self.empty_state = Empty(
            icon="\u2298",
            message="No buses scheduled",
            subtitle="Check back soon or try the other direction",
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


    def on_enter(self, *args):
        self._poller_key = POLLER.register_api(self.api, 60, lambda json: self.update(json))
        self._update_event = Clock.schedule_interval(self._update, 1)
        return super().on_enter(*args)

    def on_pre_leave(self, *args):
        if self._poller_key is not None:
            POLLER.unregister_api(self._poller_key)
            self._poller_key = None
        if self._update_event:
            self._update_event.cancel()
            self._update_event = None
        return super().on_pre_leave(*args)

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
            visible_count = 0
            if "prd" in self.data:
                arr = self.data['prd']
                for i in arr:
                    if "prdtm" in i:
                        r = i["rt"]
                        s = i["stpnm"]
                        d = i['rtdir']
                        dloc = i['des']
                        e = i['prdtm']
                        dts = dt.now()
                        dte = dt.strptime(e, '%Y%m%d %H:%M')
                        est = math.floor((dte - dts).total_seconds() / 60.0)

                        label = "{} min".format(est)
                        if est < 1:
                            label = "Now Arriving"

                        b = BusEta(route=r, stop=s, dest=d, dest_loc=dloc, eta=label)
                        if self.outbound and d == "OUTBOUND":
                            # Update live stop name from first visible arrival
                            if self.stop_lbl.text == "":
                                self.stop_lbl.text = s
                            self.grid.add_widget(b)
                            visible_count += 1
                        elif not self.outbound and d == "INBOUND":
                            if self.stop_lbl.text == "":
                                self.stop_lbl.text = s
                            self.grid.add_widget(b)
                            visible_count += 1

            direction = "outbound" if self.outbound else "inbound"
            self.empty_state.message = "No {} buses right now".format(direction)
            if visible_count == 0:
                self.empty_state.opacity = 1
            else:
                self.empty_state.opacity = 0

    def on_config_update(self, config):
        """Reload bus API credentials and re-register poller when settings change."""
        new_key    = config.get('prt', 'api_key', '')
        new_routes = config.get('prt', 'routes', '')
        new_stops  = config.get('prt', 'stops', '')

        if new_key != self.api_key or new_routes != self.routes or new_stops != self.stops:
            if self._poller_key is not None:
                POLLER.unregister_api(self._poller_key)
                self._poller_key = None

            self.api_key = new_key
            self.routes  = new_routes
            self.stops   = new_stops
            self.api = self.PRT_API.format(new_key, new_routes, new_stops)
            if self.is_open:
                self._poller_key = POLLER.register_api(self.api, 60, lambda json: self.update(json))

        super().on_config_update(config)