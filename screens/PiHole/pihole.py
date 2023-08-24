import os
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, ColorProperty
from interface.pihomescreen import PiHomeScreen
from screens.CommandCenter.commandbutton import CommandButton
from theme.theme import Theme
from util.const import CDN_ASSET

from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.metrics import dp
from util.helpers import get_app, get_config, get_poller, info, toast
from kivy.config import Config
from util.phlog import phlog

from util.tools import download_image_to_temp, execute_command


Builder.load_file("./screens/PiHole/pihole.kv")

class PiHoleScreen(PiHomeScreen):
    """
    PiHole Dashboard screen.  Quickly see summary stats of network pihole, enable, and disable
    pihole.
    """

    theme = Theme()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background_color_prime = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY, 0.8))
    background_color_secondary = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY, 0.8))

    HOST = "http://pi.hole"
    ROUTE = "/admin/api.php"
    PARAMS = "?summary&auth"


    UPDATE_FREQUENCY = 1

    is_visible = False

    domains_being_blocked = StringProperty("-")
    ads_blocked_today = StringProperty("-")
    unique_clients = StringProperty("-")
    status = StringProperty("UNKNOWN")

    pending_update = False

    def __init__(self, **kwargs):
        super(PiHoleScreen, self).__init__(**kwargs)
        # self.icon = CDN_ASSET.format("lofi_app_icon.png")
        if get_config().get('pihole', 'enabled', False):
            # Reconfigure based on settings
            self.HOST = get_config().get('pihole', 'host', "http://pi.hole")
            self.API_KEY = get_config().get('pihole', 'api_key', "")
            get_poller().register_api(self.get_pihole_uri(), self.UPDATE_FREQUENCY, lambda json: self.update(json))

            info("Registered PiHole API: {}".format(self.get_pihole_uri()))

    def get_pihole_uri(self):
        return "{}{}{}&auth={}".format(self.HOST, self.ROUTE, self.PARAMS, self.API_KEY)
    


    def toggle_pihole(self, active):
        info("PiHole toggle: {}".format(active))
        self.pending_update = True
        if active:
            self.status = "enabled"
            execute_command("curl \"{}{}{}&auth={}\"".format(self.HOST, self.ROUTE, "?enable", self.API_KEY))
        else:
            self.status = "disabled"
            toast("PiHole {} disabled for 5 minutes!".format(self.status), "warn")
            execute_command("curl \"{}{}{}&auth={}\"".format(self.HOST, self.ROUTE, "?disable=300", self.API_KEY))
        ## call api

    def on_enter(self, *args):
        self.is_visible = True
        return super().on_enter(*args)

    def on_exit(self, *args):
        self.is_visible = False
        return super().on_exit(*args)

    def update(self, data):
        # no need to update if the screen isn't visible
        if not self.is_visible:
            return

        if 'status' in data:
            self.status = data['status']

        if 'domains_being_blocked' in data:
            self.domains_being_blocked = data['domains_being_blocked']

        if 'ads_blocked_today' in data:
            self.ads_blocked_today = data['ads_blocked_today']

        if 'unique_clients' in data:
            self.unique_clients = data['unique_clients']