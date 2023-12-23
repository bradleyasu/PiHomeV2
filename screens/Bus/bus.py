from datetime import datetime as dt, timedelta
import math
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty

from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window

from components.Button.circlebutton import CircleButton
from components.Empty.empty import Empty
from components.Image.networkimage import NetworkImage
from components.Switch.switch import PiHomeSwitch
from composites.BusEta.buseta import BusEta
from interface.pihomescreen import PiHomeScreen
from theme.color import Color
from theme.theme import Theme
from util.helpers import get_app, get_config, get_poller, goto_screen, toast 
from util.tools import hex
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
        self.api_key = get_config().get('prt', 'api_key', '')
        self.routes = get_config().get('prt', 'routes', '')
        self.stops =  get_config().get('prt', 'stops', '')
        self.logo= get_config().get('prt', 'logo', '')
        self.icon = get_config().get('prt', 'logo', '')
        
        self.api = self.PRT_API.format(self.api_key, self.routes, self.stops)
        
        # Register API to be polled every 200 seconds
        get_poller().register_api(self.api, 60, lambda json: self.update(json))
        Clock.schedule_interval(self._update, 1)

        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY, 0.8)
        self.build()

    def build(self):
        layout = FloatLayout()
        self.grid = GridLayout(cols=1, spacing=dp(50), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))

        self.empty_state = Empty(message = "There are no busses coming anytime soon", size=(dp(get_app().width), dp(get_app().height)))
        self.empty_state.opacity = 0
        self.add_widget(self.empty_state)

        view = ScrollView(size_hint=(1, None), size=(get_app().width, dp(get_app().height) - (dp(80))))
        view.add_widget(self.grid);
        layout.add_widget(view)
        self.scroller = view
        
        self.logo = NetworkImage(url=self.logo, size=(dp(108), dp(56)), pos=(dp(get_app().width - 112), dp(0)))
        layout.add_widget(self.logo)


        ## Control Bar
        self.control_bar = GridLayout(rows=1, padding=(10,10,10,10), spacing=20, size_hint_y=None, size=(dp(get_app().width), dp(80)), pos=(0, dp(get_app().height) - (dp(80))))
        # s = PiHomeSwitch(on_change=(self.set_outbound))
        s = PiHomeSwitch(pos=(dp(get_app().width - 200), dp(100)))
        s.bind(enabled=lambda x, y:  self.set_outbound(y))
        self.bound_label = Label(text="INBOUND", font_size="22sp", size=(dp(200), dp(20)), color=(self.text_color))
        self.control_bar.add_widget(self.bound_label)
        self.control_bar.add_widget(s)

        layout.add_widget(self.control_bar)
        self.add_widget(layout)


    def scroll_y(self, amount):
        if self.scroller.scroll_y + amount < 0:
            self.scroller.scroll_y = 0
        elif self.scroller.scroll_y + amount > 1:
            self.scroller.scroll_y = 1
        else:
            self.scroller.scroll_y = self.scroller.scroll_y + amount

    def on_rotary_turn(self, direction, pressed):
        if direction == 1:
            self.scroll_y(-0.1)
        else:
            self.scroll_y(0.1)

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
                    
                        b = BusEta(route=r, stop=s, dest=d, dest_loc=dloc, eta=str(est)+" min")
                        if self.outbound and d == "OUTBOUND":
                            self.grid.add_widget(b)
                        elif not self.outbound and d == "INBOUND":
                            self.grid.add_widget(b)

            if no_data == True:
                self.empty_state.opacity = 1
            else:
                self.empty_state.opacity = 0