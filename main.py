import kivy
from lifxlan import LifxLAN

from kivy.app import App
from kivy.uix.button import Button

from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout

from components.Reveal.reveal import Reveal
from util.configuration import Configuration
from kivy.core.window import Window

# Run PiHome on Kivy 2.0.0
kivy.require('2.0.0')


class PiHome(App):

    def __init__(self, **kwargs):
        super(PiHome, self).__init__(**kwargs)
        self.base_config = Configuration('base.ini')
        self.height = self.base_config.get_int('window', 'height', 480)
        self.width = self.base_config.get_int('window', 'width', 800)

    def setup(self):
        Window.size = (self.width, self.height)
        self.lan = LifxLAN()


    def powerOff(self):
        lights = self.lan.get_devices_by_name(["Right Lamp"])
        lights.set_power(0)
        print("off")

    def powerOn(self):
        lights = self.lan.get_devices_by_name(["Right Lamp"])
        lights.set_power(1)
        print("on")

    # the root widget
    def build(self):
        self.setup()
        # button = Button(text=self.base_config.get('test', 'phrase', 'quit'))
        # button.bind(on_press=lambda _: PiHome.get_running_app().stop())
        # reveal = Reveal()
        # reveal2 = Reveal()
        # reveal3 = Reveal()
        # reveal.add_top_widget(Label(text="PiHome"))
        # reveal.add_bottom_widget(button)
        #
        # reveal2.add_top_widget(Label(text="Another one"))
        # reveal2.add_bottom_widget(Label(text="bottom"))
        #

        onButton = Button(text="Lights ON", size_hint=(.15, .1), pos=(20, 120))
        onButton.bind(on_press=lambda _: self.powerOn())

        offButton = Button(text="Lights OFF", size_hint=(.15, .1), pos=(20, 20))
        offButton.bind(on_press=lambda _: self.powerOff())

        layout = FloatLayout(size=(self.width, self.height))
        #
        # layout.add_widget(Button(text="test"))
        # layout.add_widget(reveal)
        # layout.add_widget(reveal2)
        # layout.add_widget(Reveal())
        layout.add_widget(onButton)
        layout.add_widget(offButton)
        return layout


# Start PiHome
PiHome().run()
