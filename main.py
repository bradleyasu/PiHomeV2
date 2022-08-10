from kivy.config import Config
Config.set('kivy', 'keyboard_mode', 'systemandmulti')
Config.set('graphics', 'verify_gl_main_thread', '0')
from threading import Thread
from components.Touch.longpressring import LongPressRing
from handlers.PiHomeErrorHandler import PiHomeErrorHandler
from networking.mqtt import MQTT

from services.weather.weather import Weather
from services.wallpaper.wallpaper import Wallpaper 

import cProfile
import sys
import subprocess
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
from components.Image.networkimage import NetworkImage

from components.Reveal.reveal import Reveal
from components.Toast.toast import Toast
from composites.AppMenu.appmenu import AppMenu

from composites.PinPad.pinpad import PinPad
from networking.poller import Poller
from screens.DevTools.devtools import DevTools
from screens.Home.home import HomeScreen
from screens.Settings.settings import SettingsScreen
from screens.Bus.bus import BusScreen 
from util.configuration import Configuration
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, SwapTransition, FallOutTransition, SwapTransition, WipeTransition, RiseInTransition
from kivy.properties import ColorProperty, NumericProperty, StringProperty
from util.helpers import get_app 
from util.tools import hex
from kivy.metrics import dp
from kivy.base import ExceptionManager 
from kivy.clock import Clock

# Run PiHome on Kivy 2.0.0
kivy.require('2.0.0')

# Hide Cursor
Window.show_cursor = platform.system() == 'Darwin'
Window.keyboard_anim_args = {"d":.2,"t":"linear"}
Window.softinput_mode = 'below_target'

class PiHome(App):

    layout = FloatLayout()
    app_menu_open = False
    toast_open = False
    web_conf = None
    wallpaper_service = None


    # App menu trigger events
    _td_ticks = 0
    _td_down = False

    def __init__(self, **kwargs):
        super(PiHome, self).__init__(**kwargs)

        #Init Base configuration
        self.base_config = Configuration('base.ini')

        self.height = self.base_config.get_int('window', 'height', 480)
        self.width = self.base_config.get_int('window', 'width', 800)
        pin = self.base_config.get('security', 'pin', '')
        self.pinpad = PinPad(on_enter=self.remove_pinpad, opacity=0, pin=pin)
        self.toast = Toast(on_reset=self.remove_toast)

        self.background = NetworkImage(
            "", 
            size=(dp(self.width), dp(self.height)), 
            pos=(0,0), 
            enable_stretch=True, 
            loader="./assets/images/default_background.jpg",  
            error="./assets/images/default_background.jpg")


        #Last step is to init services
        self.init_services()

        # Flag to indicate the application is running
        self.is_running = True
        # Create the Screenmanager


    def init_services(self):
        # Init Poller Service
        self.poller = Poller()

        #Init Weather Services
        self.weather = Weather()

        #Init Weather Services
        self.wallpaper_service = Wallpaper()

    def setup(self):
        """
        Setup default windowing positions and initialize 
        application Screens
        """
        Window.size = (self.width, self.height)
        self.screens = {
            'home': HomeScreen(name = 'home', label = "Home"),
            'settings': SettingsScreen(name = 'settings', requires_pin = True, label = "Settings", callback=lambda: self.reload_configuration()),
            'bus': BusScreen(name = 'bus', label="Bus ETA"),
            'devtools': DevTools(name = 'devtools', label="Dev Tools"),
        }

        self.appmenu = AppMenu(self.screens)
        self.appmenu_ring = LongPressRing()

        self.poller.register_api("https://cdn.pihome.io/conf.json", 60 * 2, self.update_conf)
        Clock.schedule_interval(lambda _: self._run(), 1)

        # auto update every 3 hours
        Clock.schedule_once(lambda _: self._update(), 60 * 60 * 3) 

        # Add a custom error handler for pihome
        ExceptionManager.add_handler(PiHomeErrorHandler())

    # the root widget
    def build(self):
        self.setup()

        self.layout.add_widget(self.background)

        screenManager = ScreenManager(transition=WipeTransition())

        # Add Registered Screens to screenmanager 
        for screen in self.screens.values():
            screenManager.add_widget(screen)

        # Add primary screen manager
        self.layout.add_widget(screenManager)
        self.manager = screenManager
        self.layout.bind(on_touch_down=lambda _, touch:self.on_touch_down(touch))
        self.layout.bind(on_touch_up=lambda _, touch:self.on_touch_up(touch))

        self.layout.add_widget(self.appmenu_ring)
        return self.layout

    def reload_configuration(self):
        pass

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
            self.appmenu.show_apps()
        else:
            self.appmenu.reset()
            self.layout.remove_widget(self.appmenu)

    def on_touch_down(self, touch):
        self._td_down = True
        self.appmenu_ring.set_visible(True, (touch.x - self.appmenu_ring.width/2, touch.y - self.appmenu_ring.height/2))

    def on_touch_up(self, touch):
        self._td_down = False
        self._td_ticks = 0
        self.appmenu_ring.set_visible(False)

    """
    Quit PiHome and clean up resources
    """
    def quit(self):
        self.is_running = False
        get_app().stop()
        sys.exit("PiHome Terminated")

    def remove_toast(self):
        self.toast_open = False
        self.layout.remove_widget(self.toast)

    def show_toast(self, label, level = "info", timeout = 5):
        if self.toast is None:
            print("Failed to show toast: {}".format(label))
            return
        if self.toast_open is True:
            self.remove_toast()
        self.toast_open = True
        self.layout.add_widget(self.toast)
        self.toast.pop(label=label, level=level, timeout=timeout)


    def update_conf(self, json):
        # TODO validate json
        self.web_conf = json

    def _run(self):
        # Update background url from wallpaper service
        # Other regular updates
        self.background.url = self.wallpaper_service.current
        self.background.set_stretch(self.wallpaper_service.allow_stretch)

        # Start counter if holding down
        if self._td_down == True:
            self._td_ticks = self._td_ticks + 1

        # If holding down for period, open menu
        if self._td_ticks > 1:
            self.set_app_menu_open(not self.app_menu_open)
            self._td_down = False 
            self._td_ticks = 0

    def _update(self):
        self.show_toast("PiHole will update in less than 10 seconds", level = "warn", timeout = 10)
        Clock.schedule_once(lambda : subprocess.call(['sh', './update_and_restart.sh']), 12)

    
    def _reload_background(self):
        self.background.reload()

    def on_start(self):
        h = self.base_config.get('mqtt', 'host', "")
        u = self.base_config.get('mqtt', 'user_id', "")
        p = self.base_config.get('mqtt', 'password', "")
        f = self.base_config.get('mqtt', 'feed', "pihome")
        port = self.base_config.get_int('mqtt', 'port', 8883)
        if u != "" and h != "" and p != "":
            self.mqtt = MQTT(host=h, port=port, feed = f, user=u, password=p)
        # self.profile = cProfile.Profile()
        # self.profile.enable()

    # def on_stop(self):
    #     self.profile.disable()
    #     self.profile.dump_stats('pihome.profile')
    #     self.profile.print_stats()

# Start PiHome
app = PiHome()
app.run()
# PiHome().run()

