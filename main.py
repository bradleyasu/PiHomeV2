from kivy.config import Config

from listeners.PiHomeListener import PiHomeListener

Config.set('kivy', 'keyboard_mode', 'systemandmulti')
Config.set('graphics', 'verify_gl_main_thread', '0')
# Config.set('kivy', 'exit_on_escape', '0')
# Config.set('graphics', 'window_state', 'maximized')
# Config.set('graphics', 'borderless', '1')
# Config.set('graphics', 'fullscreen', 'auto')
# Config.set('graphics', 'multisamples', '0')
# Config.set('graphics', 'maxfps', '60')
# Config.set('graphics', 'resizable', '0')
# Config.set('graphics', 'position', 'custom')
# Config.set('graphics', 'left', '0')
# Config.set('graphics', 'top', '0')
from components.Hamburger.hamburger import Hamburger
from screens.CommandCenter.commandcenter import CommandCenterScreen
from screens.DisplayImageEvent.displayimageevent import DisplayImageEvent
from screens.Lofi.lofi import LofiScreen
from screens.PiHole.pihole import PiHoleScreen
from screens.WhiteBoard.whiteboard import WhiteBoard

from util.phlog import phlog


from screens.DisplayEvent.displayevent import DisplayEvent
from screens.Music.musicplayer import MusicPlayer
from server.server import PiHomeServer
from services.audio.audioplayer import AudioPlayer
from util.const import _DISPLAY_IMAGE_SCREEN, _DISPLAY_SCREEN, _DEVTOOLS_SCREEN, _HOME_SCREEN, _MUSIC_SCREEN, _SETTINGS_SCREEN, CONF_FILE, GESTURE_CHECK, GESTURE_DATABASE, GESTURE_TRIANGLE, GESTURE_W, MQTT_COMMANDS, TEMP_DIR
from handlers.PiHomeErrorHandler import PiHomeErrorHandler
from networking.mqtt import MQTT

from services.weather.weather import Weather
from services.wallpaper.wallpaper import Wallpaper 

import cProfile
import sys
import kivy
import platform
import os
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from components.Image.networkimage import NetworkImage
from kivy.graphics import Color, Ellipse, Line

from components.Toast.toast import Toast
from composites.AppMenu.appmenu import AppMenu

from composites.PinPad.pinpad import PinPad
from networking.poller import Poller
from screens.DevTools.devtools import DevTools
from screens.Home.home import HomeScreen
from screens.Settings.settings import SettingsScreen
from screens.Bus.bus import BusScreen 
from screens.SnowCast.snowcast import SnowCast
from util.configuration import Configuration
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from util.helpers import get_app, goto_screen, simplegesture
from kivy.metrics import dp
from kivy.base import ExceptionManager 
from kivy.clock import Clock
from kivy.gesture import Gesture 
from typing import List

# Run PiHome on Kivy 2.0.0
kivy.require('2.0.0')

# Hide Cursor
Window.show_cursor = platform.system() == 'Darwin'
Window.keyboard_anim_args = {"d":.2,"t":"linear"}
Window.softinput_mode = 'below_target'
os.environ["KIVY_AUDIO"] = "audio_ffpyplayer"
os.environ["KIVY_VIDEO"] = "video_ffpyplayer"

class PiHome(App):

    layout = FloatLayout()
    app_menu_open = False
    toast_open = False
    web_conf = None
    wallpaper_service = None
    listeners: List[PiHomeListener]= []

    def __init__(self, **kwargs):
        super(PiHome, self).__init__(**kwargs)

        #Init Base configuration
        self.base_config = Configuration('base.ini')

        self.height = self.base_config.get_int('window', 'height', 480)
        self.width = self.base_config.get_int('window', 'width', 800)
        pin = self.base_config.get('security', 'pin', '')
        self.pinpad = PinPad(on_enter=self.remove_pinpad, opacity=0, pin=pin)
        self.toast = Toast(on_reset=self.remove_toast)

        self.menu_button = Hamburger()


        self.background_color = NetworkImage(
            "", 
            size=(dp(self.width), dp(self.height)), 
            pos=(0,0), 
            enable_stretch=True, 
            loader="./assets/images/default_background.jpg",  
            error="./assets/images/default_background.jpg"
        )

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
        # Setup application logger
        self.phlogger = phlog()
        
        # Init Poller Service
        self.poller = Poller()

        #Init Weather Services
        self.weather = Weather()

        #Init Weather Services
        self.wallpaper_service = Wallpaper()

        # Init Server
        self.server = PiHomeServer()

        # Init Audio Player
        self.audio_player = AudioPlayer()


    def setup(self):
        """
        Setup default windowing positions and initialize 
        application Screens
        """
        Window.size = (self.width, self.height)
        self.screens = {
            _HOME_SCREEN: HomeScreen(name = _HOME_SCREEN, label = "Home"),
            _MUSIC_SCREEN: MusicPlayer(name = _MUSIC_SCREEN, label = "Music"),
            _SETTINGS_SCREEN: SettingsScreen(name = _SETTINGS_SCREEN, requires_pin = True, label = "Settings", callback=lambda: self.reload_configuration()),
            _DEVTOOLS_SCREEN: DevTools(name = _DEVTOOLS_SCREEN, label="Dev Tools", is_hidden = False, requires_pin = True),
            _DISPLAY_SCREEN: DisplayEvent(name = _DISPLAY_SCREEN, label="Display Event", is_hidden = True),
            _DISPLAY_IMAGE_SCREEN: DisplayImageEvent(name = _DISPLAY_IMAGE_SCREEN, label="Display Image Event", is_hidden = True),
            'bus': BusScreen(name = 'bus', label="PGH Regional Transit"),
            'snowcast': SnowCast(name = 'snowcast', label="Ski Report"),
            'command_center': CommandCenterScreen(name = 'command_center', label="Command Center"),
            "lofi": LofiScreen(name = "lofi", label="Lofi Radio"),
            "pihole": PiHoleScreen(name = "pihole", label="PiHole"),
            'white_board': WhiteBoard(name = 'white_board', label="White Board"),
        }

        self.appmenu = AppMenu(self.screens)

        self.poller.register_api("https://cdn.pihome.io/conf.json", 60 * 2, self.update_conf)
        Clock.schedule_interval(lambda _: self._run(), 1)

        # Add a custom error handler for pihome
        ExceptionManager.add_handler(PiHomeErrorHandler())

    
    # the root widget
    def build(self):
        self.setup()
        self.layout.size = (self.width, self.height)
        self.layout.size_hint = (1,1)
        self.layout.pos = (0,0)

        self.layout.add_widget(self.background_color)
        self.layout.add_widget(self.background)

        screenManager = ScreenManager(transition=SlideTransition(direction="down"))

        # Add Registered Screens to screenmanager 
        for screen in self.screens.values():
            screenManager.add_widget(screen)

        # Add primary screen manager
        self.layout.add_widget(screenManager)
        self.manager = screenManager
        self.layout.bind(on_touch_down=lambda _, touch:self.on_touch_down(touch))
        self.layout.bind(on_touch_up=lambda _, touch:self.on_touch_up(touch))
        self.layout.bind(on_touch_move=lambda _, touch:self.on_touch_move(touch))


        self.menu_button.pos = (dp(10), dp(400))
        self.menu_button.event_handler = lambda value: self.set_app_menu_open(value)
        self.menu_button.size_hint = (None, None)
        self.layout.add_widget(self.menu_button, index=0)

        return self.layout

    def reload_configuration(self):
        self.phlogger.info("Confgiruation changes have been made.  Resetting services....")
        self.base_config = Configuration(CONF_FILE)
        self.wallpaper_service.restart()
        self.notify_listeners("configuration_update", self.base_config)
        self.phlogger.info("Confgiuration changes have been applied!")

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
        if self.manager.transition.direction == "down":
            self.manager.transition.direction = "up"
        else:
            self.manager.transition.direction = "down"
        pin_required = pin_required and self.screens[screen].requires_pin
        if pin_required:
            self.show_pinpad()
            self.pinpad.on_enter = lambda *args: self.goto_screen(screen, False)
        else:
            self.remove_pinpad()
            self.manager.current = screen
        
        if (screen == _SETTINGS_SCREEN):
            self.menu_button.opacity = 0
        else:
            self.menu_button.opacity = 1

    def get_config(self):
        return self.base_config;

    def get_poller(self):
        return self.poller;

    def set_app_menu_open(self, open):
        if self.pinpad.opacity == 1:
            return
        self.app_menu_open = open
        if open == True:
            self.layout.add_widget(self.appmenu, index=1)
            self.appmenu.show_apps()
        else:
            self.appmenu.reset()
            self.layout.remove_widget(self.appmenu)
            self.menu_button.is_open = False

    def toggle_app_menu(self):
        self.set_app_menu_open(not self.app_menu_open)

    def on_touch_down(self, touch):
        # start collecting points in touch.ud
        # create a line to display the points
        userdata = touch.ud
        userdata['line'] = Line(points=(touch.x, touch.y))
        return False 

    def on_touch_up(self, touch):
        g = simplegesture('', list(zip(touch.ud['line'].points[::2], touch.ud['line'].points[1::2])))

        # User Input Gesture
        # print(self.gdb.gesture_to_str(g))
        # print(GESTURE_DATABASE.gesture_to_str(g))
        
        # print match scores between all known gestures
        # print("check:", g.get_score(GESTURE_CHECK))

        # use database to find the more alike gesture, if any
        g2 = GESTURE_DATABASE.find(g, minscore=0.70)
        # print(g2)
        if g2:
            if g2[1] == GESTURE_CHECK:
                pass
                # self.set_app_menu_open(not self.app_menu_open)
            elif g2[1] == GESTURE_TRIANGLE:
                # goto_screen(_DEVTOOLS_SCREEN)
                pass
            elif g2[1] == GESTURE_W:
                # self.wallpaper_service.shuffle()
                pass
            

    def on_touch_move(self, touch):
        # store points of the touch movement
        try:
            touch.ud['line'].points += [touch.x, touch.y]
            return False 
        except (KeyError) as e:
            pass

    def get_screen_shot(self):
        """
        Get a screenshot of the current screen
        """
        Window.screenshot(name=TEMP_DIR + "/screenshot.png")


    def add_listener(self, listener: PiHomeListener):
        self.listeners.append(listener)

    def notify_listeners(self, type, payload):
        for listener in self.listeners:
            if listener.type == type:
                listener.callback(payload)

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
        # important
        self.web_conf = json

    def _run(self):
        # Update background url from wallpaper service
        # Other regular updates
        self.background.url = self.wallpaper_service.current
        self.background_color.url = self.wallpaper_service.current_color
        self.background.set_stretch(self.wallpaper_service.allow_stretch)

    
    def _reload_background(self):
        """
        Updates the background image, clearing the cache
        """
        self.background.reload()
        self.background_color.reload()

    def on_start(self):
        """
        When application has started, do the following:
         - Setup MQTT Services
         - If in debug mode, setup Profiler
        """
        self._init_mqtt()

        # Make temporary dir 
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)
        # self.profile = cProfile.Profile()
        # self.profile.enable()
        self.server.start_server()

    def _init_mqtt(self):
        h = self.base_config.get('mqtt', 'host', "")
        u = self.base_config.get('mqtt', 'user_id', "")
        p = self.base_config.get('mqtt', 'password', "")
        f = self.base_config.get('mqtt', 'feed', "pihome")
        port = self.base_config.get_int('mqtt', 'port', 8883)
        if u != "" and h != "" and p != "":
            self.mqtt = MQTT(host=h, port=port, feed = f, user=u, password=p)
            self.mqtt.add_listener(type = "app", callback = lambda payload: Clock.schedule_once(lambda _: goto_screen(payload["key"]), 0))
            self.mqtt.add_listener(type = "display", callback = lambda payload: Clock.schedule_once(lambda _: self._handle_display_event(payload), 0))
            self.mqtt.add_listener(type = "image", callback = lambda payload: Clock.schedule_once(lambda _: self._handle_display_image_event(payload), 0))
            self.mqtt.add_listener(type = "command", callback = lambda payload: self._handle_command_event(payload))
            self.mqtt.add_listener(type = "toast", callback = lambda payload: Clock.schedule_once(lambda _: self.show_toast(payload["message"], payload["level"], payload["timeout"]), 0))
 
    def _handle_command_event(self, payload):
        cmd = payload["execute"]
        if cmd in MQTT_COMMANDS:
            MQTT_COMMANDS[cmd]()

    def _handle_display_event(self, payload):
        if "title" in payload and "message" in payload and "image" in payload:
            self.screens[_DISPLAY_SCREEN].title = payload["title"]
            self.screens[_DISPLAY_SCREEN].message = payload["message"]
            self.screens[_DISPLAY_SCREEN].image = payload["image"]
            if "background" in payload:
                self.screens[_DISPLAY_SCREEN].set_background(payload["background"])
            if "timeout" in payload:
                self.screens[_DISPLAY_SCREEN].set_timeout(payload["timeout"], self.manager.current_screen.name)
            goto_screen(_DISPLAY_SCREEN)


    def _handle_display_image_event(self, payload):
        if "image_url" in payload:
            self.screens[_DISPLAY_IMAGE_SCREEN].image = payload["image_url"]
            if "timeout" in payload:
                self.screens[_DISPLAY_IMAGE_SCREEN].set_timeout(payload["timeout"], self.manager.current_screen.name)

            if "reload_interval" in payload:
                self.screens[_DISPLAY_IMAGE_SCREEN].reload_interval = int(payload["reload_interval"])

            goto_screen(_DISPLAY_IMAGE_SCREEN)


    def on_stop(self):
        self.server.stop_server()
        self.phlogger.info("=================================== PIHOME SHUTDOWN ===================================")
    #     self.profile.disable()
    #     self.profile.dump_stats('pihome.profile')
    #     self.profile.print_stats()

# Start PiHome
app = PiHome()
app.run()
# PiHome().run()

