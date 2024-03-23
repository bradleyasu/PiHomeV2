import json
import os
from kivy.lang import Builder
from kivy.properties import ColorProperty, NumericProperty, StringProperty, ObjectProperty
from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from services.audio.sfx import SFX
from theme.color import Color
from theme.theme import Theme

from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

from kivy.clock import Clock

from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/UberEats/UberEats.kv")

ORDER_SCRIPT = "./screens/UberEats/orders.sh"

class UberEatsScreen(PiHomeScreen):
    """
    PiHole Dashboard screen.  Quickly see summary stats of network pihole, enable, and disable
    pihole.
    """

    theme = Theme()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background_color= ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY, 0.8))
    background_color_secondary = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY, 0.8))

    tick_color = ColorProperty(theme.hextorgb(Color.DARK_CELERY_600))
    tick_color_disabled = ColorProperty(theme.hextorgb(Color.DARK_GRAY_200))


    error_message = StringProperty("")
    error_size_hint = ObjectProperty((1, 0))

    title = StringProperty("No Orders")
    order_count = NumericProperty(0)
    marker_latitude = NumericProperty(0)
    marker_longitude = NumericProperty(0)

    def __init__(self, **kwargs):
        super(UberEatsScreen, self).__init__(**kwargs)
        if not os.path.exists(ORDER_SCRIPT):
            PIHOME_LOGGER.error("Uber Eats order script not found")
            self.set_error("Please check the readme for installation instructions.")
        else:
            Clock.schedule_interval(lambda _:self.order_poll(), 60)

    def on_order_count(self, instance, value):
        if value > 0:
            PIHOME_SCREEN_MANAGER.goto(self.name)
            SFX.play("long_notify")

    def on_error_message(self, instance, value):
        if value is not None and value != "":
            self.error_size_hint = (1, 1)
        else:
            self.error_size_hint = (1, 0)
    
    def order_poll(self):
        # Execute the order.sh script and get the output
        output = os.popen('bash {}'.format(ORDER_SCRIPT)).read()

        # confirm output is not empty and there were not errors
        if output == "":
            self.set_error("{} script returned no output".format(ORDER_SCRIPT))
            return

        #convert to json object
        output = json.loads(output)
        if not 'data' in output:
            self.set_error("{} script executed by there is no data in the output".format(ORDER_SCRIPT))
            return
        data = output['data']
        orders = data['orders']

        self.order_count = len(orders)
        if len(orders) > 0:
            try:
                order = orders[0]
                overview = order['activeOrderOverview']
                courier = order['backgroundFeedCards'][0]
                courier_location = courier['mapEntity'][0]
                self.title = overview['title']
                self.marker_latitude = courier_location['latitude']
                self.marker_longitude = courier_location['longitude']
            except Exception as e:
                self.set_error("Error parsing order data: {}".format(e))
                return

        self.set_error(None)

    def set_error(self, error=None):
        if error is None:
            self.error_message = ""
        else:
            self.error_message = error