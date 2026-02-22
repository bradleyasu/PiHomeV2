import os
import platform

# CRITICAL: Set environment variables BEFORE any imports that might initialize SDL/audio
# Disable Kivy audio - we use direct ffmpeg/ffplay subprocess calls instead
# This prevents audio backend from probing/interfering with hw:1,0 (DAC)
os.environ["KIVY_AUDIO"] = "sdl2"  # SDL2 won't initialize on headless systems
os.environ["KIVY_VIDEO"] = "null"
# Prevent SDL2 from probing audio devices entirely
os.environ["SDL_AUDIODRIVER"] = "dummy"
# Additional SDL environment variables to prevent audio interference
os.environ["SDL_DISKAUDIO_NWRITE"] = "0"  # Disable disk audio
os.environ["SDL_DISKAUDIODEVICE"] = "/dev/null"  # Redirect disk audio
os.environ["AUDIODEV"] = "/dev/null"  # Prevent ALSA device enumeration
# Use EGL window provider on Raspberry Pi to avoid SDL audio interference
# On other platforms (macOS, etc.) use default SDL2
if platform.system() == 'Linux':
    # Only use egl_rpi on Linux (Raspberry Pi)
    os.environ["KIVY_WINDOW"] = "egl_rpi"
# Prevent pygame from initializing if accidentally imported
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

# Now safe to import modules (after env vars are set)
from networking.poller import POLLER
from services.homeassistant.homeassistant import HOME_ASSISTANT

from kivy.config import Config
from kivy.graphics import Line
from composites.TimerDrawer.timerdrawer import TIMER_DRAWER
from services.taskmanager.taskmanager import TASK_MANAGER

Config.set('kivy', 'keyboard_mode', 'systemandmulti')
Config.set('graphics', 'verify_gl_main_thread', '0')

# NOW safe to import screen manager - it uses a lazy proxy that won't instantiate
# until first accessed, which happens after Config.set() above
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER

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
import signal
import kivy
import platform
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from components.Image.networkimage import NetworkImage  # Keep imported for .kv files
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

    layout = FloatLayout()
    app_menu_open = False
    toast_open = False
    web_conf = None

    def __init__(self, **kwargs):
        super(PiHome, self).__init__(**kwargs)

        self.height = CONFIG.get_int('window', 'height', 480)
        self.width = CONFIG.get_int('window', 'width', 800)
        self.toast = Toast(on_reset=self.remove_toast)

        self.menu_button = Hamburger()

        # Flag to indicate the application is running
        self.is_running = True


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
        self.layout.size_hint = (1, 1)  # Use percentage to fill window
        self.layout.pos = (0,0)


        self.layout.bind(on_touch_down=lambda _, touch:self.on_touch_down(touch))
        self.layout.bind(on_touch_up=lambda _, touch:self.on_touch_up(touch))
        self.layout.bind(on_touch_move=lambda _, touch:self.on_touch_move(touch))


        self.menu_button.pos = (dp(10), dp(400))
        self.menu_button.event_handler = lambda value: self.set_app_menu_open(value)
        self.menu_button.size_hint = (None, None)
        
        # Add primary screen manager with integrated background
        # Background is rendered in ScreenManager's canvas.before to ensure proper z-ordering
        PIHOME_SCREEN_MANAGER.size = (self.width, self.height)
        PIHOME_SCREEN_MANAGER.size_hint = (1, 1)
        
        # Load default background initially
        try:
            from kivy.core.image import Image as CoreImage
            default_bg = "./assets/images/default_background.jpg"
            if os.path.exists(default_bg):
                texture = CoreImage(default_bg, keep_data=True).texture
                PIHOME_SCREEN_MANAGER.set_background_texture(texture)
                PIHOME_LOGGER.info("Default background loaded")
        except Exception as e:
            PIHOME_LOGGER.error(f"Failed to load default background: {e}")
        
        self.layout.add_widget(PIHOME_SCREEN_MANAGER)
        
        # Force screen loading if on_parent didn't trigger it
        if not PIHOME_SCREEN_MANAGER.screens_loaded:
            PIHOME_LOGGER.warning("Screens not loaded in on_parent, loading manually...")
            PIHOME_SCREEN_MANAGER.load_screens()
        
        PIHOME_LOGGER.info(f"Screen manager has {len(PIHOME_SCREEN_MANAGER.loaded_screens)} screens loaded")
        PIHOME_LOGGER.info(f"Current screen: {PIHOME_SCREEN_MANAGER.current}")
        
        self.layout.add_widget(TIMER_DRAWER)
        self.layout.add_widget(self.menu_button)

        # Startup TaskManager - only if task screen is loaded
        if _TASK_SCREEN in PIHOME_SCREEN_MANAGER.loaded_screens:
            TASK_MANAGER.start(PIHOME_SCREEN_MANAGER.loaded_screens[_TASK_SCREEN])
        else:
            # Retry after screens are loaded
            Clock.schedule_once(lambda dt: TASK_MANAGER.start(PIHOME_SCREEN_MANAGER.loaded_screens.get(_TASK_SCREEN)), 0.5)

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
        PIHOME_LOGGER.info("PiHome shutting down...")
        self.is_running = False
        
        # Stop server first
        try:
            SERVER.stop_server()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error stopping server: {e}")
        
        # Cleanup audio device
        try:
            from services.audio.audioplayernew import AUDIO_PLAYER
            AUDIO_PLAYER.cleanup()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error cleaning up audio: {e}")
        
        # Cleanup SFX processes
        try:
            from services.audio.sfx import SFX
            SFX.cleanup()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error cleaning up SFX: {e}")
        
        # Stop Kivy app
        try:
            self.stop()
        except Exception as e:
            PIHOME_LOGGER.error(f"Error stopping Kivy app: {e}")
        
        PIHOME_LOGGER.info("PiHome terminated")
        # Force exit to ensure we don't hang
        os._exit(0)

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
        # Update background texture from wallpaper service
        from kivy.core.image import Image as CoreImage
        from kivy.loader import Loader
        
        try:
            wallpaper_path = WALLPAPER_SERVICE.current
            if wallpaper_path and wallpaper_path != "":
                # Use Kivy's async loader for better performance with URLs
                if wallpaper_path.startswith('http'):
                    proxyimg = Loader.image(wallpaper_path)
                    if proxyimg.loaded:
                        PIHOME_SCREEN_MANAGER.set_background_texture(proxyimg.texture)
                    else:
                        # Bind to load event for async loading
                        def on_img_load(instance):
                            PIHOME_SCREEN_MANAGER.set_background_texture(instance.texture)
                        proxyimg.bind(on_load=on_img_load)
                else:
                    # For local files, load directly
                    if os.path.exists(wallpaper_path):
                        texture = CoreImage(wallpaper_path, keep_data=True).texture
                        PIHOME_SCREEN_MANAGER.set_background_texture(texture)
        except Exception as e:
            PIHOME_LOGGER.debug(f"Background update: {e}")

    
    def _reload_background(self):
        """
        Updates the background image, clearing the cache
        """
        from kivy.loader import Loader
        current_path = WALLPAPER_SERVICE.current
        if current_path:
            # Clear from cache if it's a URL
            if current_path.startswith('http'):
                Loader.image(current_path).reload()
            # Force reload by calling _run
            self._run()

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
        # Cleanup audio device if not already done
        if self.is_running:
            try:
                from services.audio.audioplayernew import AUDIO_PLAYER
                AUDIO_PLAYER.cleanup()
            except Exception as e:
                PIHOME_LOGGER.error(f"Error cleaning up audio: {e}")
            try:
                SERVER.stop_server()
            except Exception as e:
                PIHOME_LOGGER.error(f"Error stopping server: {e}")
        PIHOME_LOGGER.info("=================================== PIHOME SHUTDOWN ===================================")
    #     self.profile.disable()
    #     self.profile.dump_stats('pihome.profile')
    #     self.profile.print_stats()

def signal_handler(sig, frame):
    """Handle SIGINT (CTRL+C) and SIGTERM gracefully"""
    PIHOME_LOGGER.info(f"Received signal {sig}, shutting down...")
    try:
        if app and hasattr(app, 'quit'):
            app.quit()
        else:
            sys.exit(0)
    except Exception as e:
        PIHOME_LOGGER.error(f"Error during shutdown: {e}")
        sys.exit(1)

# Start PiHome
app = PiHome()

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try:
    app.run()
except KeyboardInterrupt:
    PIHOME_LOGGER.info("KeyboardInterrupt received, shutting down...")
    app.quit()

