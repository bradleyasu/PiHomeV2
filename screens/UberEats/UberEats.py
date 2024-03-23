import json
import os
from kivy.lang import Builder
from kivy.properties import ColorProperty, NumericProperty
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

    order_count = NumericProperty(0)

    def __init__(self, **kwargs):
        super(UberEatsScreen, self).__init__(**kwargs)
        if not os.path.exists(ORDER_SCRIPT):
            PIHOME_LOGGER.error("Uber Eats order script not found")
        else:
            Clock.schedule_interval(lambda _:self.order_poll(), 60)

    def on_order_count(self, instance, value):
        if value > 0:
            PIHOME_SCREEN_MANAGER.goto(self.name)
            SFX.play("long_notify")
    
    def order_poll(self):
        # Execute the order.sh script and get the output
        output = os.popen('bash {}'.format(ORDER_SCRIPT)).read()
        #convert to json object
        output = json.loads(output)
        data = output['data']
        orders = data['orders']

        self.order_count = len(orders)