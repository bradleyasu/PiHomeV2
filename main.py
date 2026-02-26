import os

from networking.poller import POLLER
from services.homeassistant.homeassistant import HOME_ASSISTANT

os.environ["KIVY_AUDIO"] = "ffpyplayer"
os.environ["KIVY_VIDEO"] = "video_ffpyplayer"

from kivy.config import Config
from kivy.graphics import Line
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from services.taskmanager.taskmanager import TASK_MANAGER
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER

Config.set('kivy', 'keyboard_mode', 'systemandmulti')
Config.set('graphics', 'verify_gl_main_thread', '0')
from components.Hamburger.hamburger import Hamburger

from networking.poller import POLLER
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER 

from server.server import SERVER
from util.const import _TASK_SCREEN, GESTURE_CHECK, GESTURE_DATABASE, GESTURE_TRIANGLE, GESTURE_W, TEMP_DIR
from handlers.PiHomeErrorHandler import PiHomeErrorHandler
from networking.mqtt import MQTT

from services.wallpaper.wallpaper import WALLPAPER_SERVICE 
import sys
import kivy
import platform
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from components.Image.networkimage import NetworkImage
from kivy.graphics import Line

from components.Toast.toast import Toast

from util.configuration import CONFIG
from kivy.core.window import Window
from util.helpers import get_app, simplegesture
from kivy.metrics import dp
from kivy.base import ExceptionManager 
from kivy.clock import Clock
from kivy.gesture import Gesture 

# Run PiHome on Kivy 2.0.0
kivy.require('2.0.0')

# Hide Cursor
Window.show_cursor = platform.system() == 'Darwin'
Window.keyboard_anim_args = {"d":.2,"t":"linear"}
Window.softinput_mode = 'below_target'

class PiHome(App):

    app_menu_open = False
    toast_open = False
    web_conf = None

    def __init__(self, **kwargs):
        super(PiHome, self).__init__(**kwargs)
        
        # Create layout as instance variable, not class variable
        # This ensures it's created after Window is properly initialized
        # Critical for Raspberry Pi OpenGL ES rendering
        self.layout = FloatLayout()

        self.height = CONFIG.get_int('window', 'height', 480)
        self.width = CONFIG.get_int('window', 'width', 800)
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



        # Flag to indicate the application is running
        self.is_running = True
        # Create the Screenmanager


    def setup(self):
        """
        Setup default windowing positions and initialize 
        application Screens
        """
        Window.size = (self.width, self.height)

        POLLER.register_api("https://cdn.pihome.io/conf.json", 60 * 2, self.update_conf)
        Clock.schedule_interval(lambda _: self._run(), 1)

        # Connect to home assistant
        HOME_ASSISTANT.connect()

        # Add a custom error handler for pihome
        ExceptionManager.add_handler(PiHomeErrorHandler())

    # the root widget
    def build(self):
        self.setup()
        self.layout.size = (self.width, self.height)
        self.layout.size_hint = (1,1)
        self.layout.pos = (0,0)


        self.layout.bind(on_touch_down=lambda _, touch:self.on_touch_down(touch))
        self.layout.bind(on_touch_up=lambda _, touch:self.on_touch_up(touch))
        self.layout.bind(on_touch_move=lambda _, touch:self.on_touch_move(touch))


        self.menu_button.pos = (dp(10), dp(400))
        self.menu_button.event_handler = lambda value: self.set_app_menu_open(value)
        self.menu_button.size_hint = (None, None)
        
        # Ensure backgrounds have fixed sizes (no auto-sizing) for consistent rendering on Pi
        self.background_color.size_hint = (None, None)
        self.background.size_hint = (None, None)
        
        # NOTE: Widget rendering order is critical here.
        self.layout.add_widget(self.background_color)  # Will be at bottom
        self.layout.add_widget(self.background)  # On top of background_color
        
        # Explicitly add foreground widgets at index 0 to ensure they're always on top
        # This is necessary for proper rendering on Raspberry Pi touchscreen
        self.layout.add_widget(PIHOME_SCREEN_MANAGER)
        # self.layout.add_widget(TIMER_DRAWER)
        # self.layout.add_widget(self.menu_button)

        # Startup TaskManager
        # TASK_MANAGER.start(PIHOME_SCREEN_MANAGER.loaded_screens[_TASK_SCREEN])

        return self.layout
    
    def reload_configuration(self):
        PIHOME_LOGGER.info("Confgiruation changes have been made.  Resetting services....")
        # CONFIG = Configuration(CONF_FILE)
        WALLPAPER_SERVICE.restart()
        PIHOME_SCREEN_MANAGER.reload_all(CONFIG)
        PIHOME_LOGGER.info("Confgiuration changes have been applied!")

    def restart(self):
        """
        Clean kivy widgets and restart the application
        """
        self.root.clear_widgets()
        self.stop()
        return PiHome().run()

    def get_size(self):
        return (self.width, self.height)

    
    # def goto_screen(self, screen, pin_required = True):
    #     """
    #     Navigate to a specific screen.  If the PIN is required to access the
    #     screen, the pin pad will be displayed prompting the user to enter PIN
    #     """
    #     if self.manager.transition.direction == "down":
    #         self.manager.transition.direction = "up"
    #     else:
    #         self.manager.transition.direction = "down"
    #     pin_required = pin_required and self.screens[screen].requires_pin
    #     if pin_required:
    #         self.show_pinpad()
    #         self.pinpad.on_enter = lambda *args: self.goto_screen(screen, False)
    #     else:
    #         self.remove_pinpad()
    #         self.manager.current = screen
        
    #     if (screen == _SETTINGS_SCREEN):
    #         self.menu_button.opacity = 0
    #     else:
    #         self.menu_button.opacity = 1

    def set_app_menu_open(self, open):
        # if self.pinpad.opacity == 1:
            # return
        self.app_menu_open = open
        if open == True:
            # self.layout.add_widget(self.appmenu, index=1)
            # self.appmenu.show_apps()
            PIHOME_SCREEN_MANAGER.app_menu.show()
        else:
            # self.appmenu.reset()
            # self.layout.remove_widget(self.appmenu)
            PIHOME_SCREEN_MANAGER.app_menu.hide()
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


    """
    Quit PiHome and clean up resources
    """
    def quit(self):
        self.is_running = False
        # Cleanup audio device before exit
        try:
            from services.audio.audioplayernew import AUDIO_PLAYER
            AUDIO_PLAYER.cleanup()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error cleaning up audio: {e}")
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
        self.background.url = WALLPAPER_SERVICE.current
        self.background_color.url = WALLPAPER_SERVICE.current_color
        self.background.set_stretch(WALLPAPER_SERVICE.allow_stretch)

    
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
        SERVER.start_server()

    def _init_mqtt(self):
        h = CONFIG.get('mqtt', 'host', "")
        u = CONFIG.get('mqtt', 'user_id', "")
        p = CONFIG.get('mqtt', 'password', "")
        f = CONFIG.get('mqtt', 'feed', "pihome")
        port = CONFIG.get_int('mqtt', 'port', 8883)
        if u != "" and h != "" and p != "":
            self.mqtt = MQTT(host=h, port=port, feed = f, user=u, password=p)
 

    def on_stop(self):
        # Cleanup audio device
        try:
            from services.audio.audioplayernew import AUDIO_PLAYER
            AUDIO_PLAYER.cleanup()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error cleaning up audio: {e}")
        SERVER.stop_server()
        PIHOME_LOGGER.info("=================================== PIHOME SHUTDOWN ===================================")
    #     self.profile.disable()
    #     self.profile.dump_stats('pihome.profile')
    #     self.profile.print_stats()

# Start PiHome
app = PiHome()
app.run()
# PiHome().run()

