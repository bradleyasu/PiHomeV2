import sys
import time
import kivy
import platform
from kivy.app import App
from kivy.uix.button import Button

from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from components.Button.circlebutton import CircleButton

from components.Reveal.reveal import Reveal
from composites.AppMenu.appmenu import AppMenu

from composites.PinPad.pinpad import PinPad
from networking.poller import Poller
from screens.Home.home import HomeScreen
from screens.Settings.settings import SettingsScreen
from screens.Bus.bus import BusScreen 
from util.configuration import Configuration
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, SwapTransition
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from util.helpers import get_app 
from util.tools import hex
from kivy.metrics import dp
from kivy.clock import Clock

# Run PiHome on Kivy 2.0.0
kivy.require('2.0.0')

# Hide Cursor
Window.show_cursor = platform.system() == 'Darwin'

class PiHome(App):

    layout = FloatLayout()
    app_menu_open = False
    def __init__(self, **kwargs):
        super(PiHome, self).__init__(**kwargs)
        self.poller = Poller();
        self.base_config = Configuration('base.ini')
        self.height = self.base_config.get_int('window', 'height', 480)
        self.width = self.base_config.get_int('window', 'width', 800)
        pin = self.base_config.get('security', 'pin', '')
        self.pinpad = PinPad(on_enter=self.remove_pinpad, opacity=0, pin=pin)

        
        # Flag to indicate the application is running
        self.is_running = True
        # Create the Screenmanager

    def setup(self):
        """
        Setup default windowing positions and initialize 
        application Screens
        """
        Window.size = (self.width, self.height)
        self.screens = {
            'home': HomeScreen(name = 'home'),
            'settings': SettingsScreen(name = 'settings', requires_pin = True),
            'bus': BusScreen(name = 'bus', icon = self.base_config.get('bus', 'logo', ''))
        }

        self.appmenu = AppMenu(self.screens)

    # the root widget
    def build(self):
        self.setup()
        screenManager = ScreenManager(transition=SwapTransition())

        # layout.add_widget(Button(text="test"))
        # layout.add_widget(reveal)
        # layout.add_widget(reveal2)
        # layout.add_widget(Reveal())

        # Add Registered Screens to screenmanager 
        for screen in self.screens.values():
            screenManager.add_widget(screen)


        # Add primary screen manager
        self.layout.add_widget(screenManager)

        # Add global accessible pinpad widget
        # self.layout.add_widget(self.pinpad)


        self.manager = screenManager

        self.layout.bind(on_touch_down=lambda _, touch:self.on_touch_down(touch))
        return self.layout

    def restart(self):
        """
        Clean kivy widgets and restart the application
        """
        self.root.clear_widgets()
        self.stop()
        return PiHome().run()

    def show_pinpad(self):
        """
        Show the lock screen/pin pad view
        """
        self.layout.add_widget(self.pinpad)
        self.pinpad.opacity = 1
        self.pinpad.animate()

    def remove_pinpad(self, *args):
        self.layout.remove_widget(self.pinpad)
        self.pinpad.opacity = 0
        self.pinpad.reset()

    def get_size(self):
        return (self.width, self.height)

    
    def goto_screen(self, screen, pin_required = True):
        """
        Navigate to a specific screen.  If the PIN is required to access the
        screen, the pin pad will be displayed prompting the user to enter PIN
        """
        pin_required = pin_required and self.screens[screen].requires_pin
        if pin_required:
            self.show_pinpad()
            self.pinpad.on_enter = lambda *args: self.goto_screen(screen, False)
        else:
            self.remove_pinpad()
            self.manager.current = screen

    def get_config(self):
        return self.base_config;

    def get_poller(self):
        return self.poller;

    def set_app_menu_open(self, open):
        self.app_menu_open = open
        if open == True:
            self.layout.add_widget(self.appmenu)
        else:
            self.layout.remove_widget(self.appmenu)

    def on_touch_down(self, touch):
        if touch.is_double_tap:
            self.set_app_menu_open(not self.app_menu_open)

    """
    Quit PiHome and clean up resources
    """
    def quit(self):
        self.is_running = False
        get_app().stop()
        sys.exit("PiHome Terminated")

# Start PiHome
PiHome().run()
