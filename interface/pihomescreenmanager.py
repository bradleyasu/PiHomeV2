import json
import os
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.screenmanager import SlideTransition
from kivy.uix.screenmanager import SwapTransition, FadeTransition, NoTransition
from kivy.graphics import Color, Rectangle
from components.PulseWidget.PulseWidget import PULSER
from composites.PinPad.pinpad import PinPad
from system.rotary import ROTARY_ENCODER
from util.configuration import CONFIG
from util.phlog import PIHOME_LOGGER
from kivy.clock import Clock
from kivy.loader import Loader

class PiHomeScreenManager(ScreenManager):
    screens_loaded = False
    loaded_screens = {}
    app_menu = None

    def __init__(self, **kwargs):
        super(PiHomeScreenManager, self).__init__(**kwargs)

        # Background images for wallpaper
        self._background_color_texture = None
        self._background_texture = None
        self._current_wallpaper_url = ""
        self._current_wallpaper_color_url = ""
        self._allow_stretch = True
        
        # Setup background rendering on canvas
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_color_rect = Rectangle(pos=self.pos, size=self.size)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        
        # Update background when size/pos changes
        self.bind(pos=self._update_bg, size=self._update_bg)
        
        # Schedule wallpaper updates
        Clock.schedule_interval(lambda dt: self._update_wallpaper(), 1)

        self.rotary_encoder = ROTARY_ENCODER
        if self.rotary_encoder.is_initialized:
            self.rotary_encoder.button_callback = lambda long_press: self._rotary_pressed(long_press)
            self.rotary_encoder.update_callback = lambda direction, pressed: self._rotary_handler(direction, pressed)
            self.rotary_encoder.button_on_down_callback = lambda: self._rotary_on_down()
    
    def _update_bg(self, *args):
        """Update background rectangle to match widget size/position"""
        if self._allow_stretch:
            self.bg_color_rect.pos = self.pos
            self.bg_color_rect.size = self.size
            self.bg_rect.pos = self.pos
            self.bg_rect.size = self.size
        else:
            # Keep aspect ratio - this will be handled when texture loads
            self._update_texture_sizing()
    
    def _update_texture_sizing(self):
        """Update texture sizing based on stretch mode"""
        try:
            if self._allow_stretch:
                self.bg_color_rect.pos = self.pos
                self.bg_color_rect.size = self.size
                self.bg_rect.pos = self.pos
                self.bg_rect.size = self.size
            else:
                # Keep aspect ratio for both textures
                if self._background_color_texture:
                    self._apply_aspect_ratio(self.bg_color_rect, self._background_color_texture)
                if self._background_texture:
                    self._apply_aspect_ratio(self.bg_rect, self._background_texture)
        except Exception as e:
            PIHOME_LOGGER.error("Error updating texture sizing: {}".format(e))
    
    def _apply_aspect_ratio(self, rect, texture):
        """Apply aspect ratio sizing to a rectangle with a texture"""
        if not texture:
            return
        
        aspect = texture.width / float(texture.height)
        w_aspect = self.width / float(self.height)
        
        if aspect > w_aspect:
            # Image is wider
            new_width = self.width
            new_height = self.width / aspect
        else:
            # Image is taller
            new_height = self.height
            new_width = self.height * aspect
        
        # Center the image
        rect.size = (new_width, new_height)
        rect.pos = (
            self.x + (self.width - new_width) / 2,
            self.y + (self.height - new_height) / 2
        )
    
    def _update_wallpaper(self):
        """Update wallpaper from WALLPAPER_SERVICE"""
        try:
            from services.wallpaper.wallpaper import WALLPAPER_SERVICE
        except ImportError:
            return  # Service not ready yet
        
        try:
            # Check if stretch mode changed
            if self._allow_stretch != WALLPAPER_SERVICE.allow_stretch:
                self._allow_stretch = WALLPAPER_SERVICE.allow_stretch
                self._update_texture_sizing()
            
            # Update background color if changed
            if self._current_wallpaper_color_url != WALLPAPER_SERVICE.current_color:
                self._current_wallpaper_color_url = WALLPAPER_SERVICE.current_color
                if self._current_wallpaper_color_url:
                    proxyimg = Loader.image(self._current_wallpaper_color_url, nocache=False)
                    proxyimg.bind(on_load=lambda img: self._set_bg_color_texture(img.texture))
            
            # Update background if changed
            if self._current_wallpaper_url != WALLPAPER_SERVICE.current:
                self._current_wallpaper_url = WALLPAPER_SERVICE.current
                if self._current_wallpaper_url:
                    proxyimg = Loader.image(self._current_wallpaper_url, nocache=False)
                    proxyimg.bind(on_load=lambda img: self._set_bg_texture(img.texture))
        except Exception as e:
            PIHOME_LOGGER.error("Error updating wallpaper: {}".format(e))
    
    def _set_bg_color_texture(self, texture):
        """Set the background color texture"""
        try:
            self._background_color_texture = texture
            self.bg_color_rect.texture = texture
            self._update_texture_sizing()
        except Exception as e:
            PIHOME_LOGGER.error("Error setting background color texture: {}".format(e))
    
    def _set_bg_texture(self, texture):
        """Set the background texture"""
        try:
            self._background_texture = texture
            self.bg_rect.texture = texture
            self._update_texture_sizing()
        except Exception as e:
            PIHOME_LOGGER.error("Error setting background texture: {}".format(e))
    
    def reload_background(self):
        """Force reload backgrounds from cache"""
        if self._current_wallpaper_url:
            try:
                Loader.image(self._current_wallpaper_url).remove_from_cache()
            except:
                pass
            proxyimg = Loader.image(self._current_wallpaper_url, nocache=True)
            proxyimg.bind(on_load=lambda img: self._set_bg_texture(img.texture))
        
        if self._current_wallpaper_color_url:
            try:
                Loader.image(self._current_wallpaper_color_url).remove_from_cache()
            except:
                pass
            proxyimg = Loader.image(self._current_wallpaper_color_url, nocache=True)
            proxyimg.bind(on_load=lambda img: self._set_bg_color_texture(img.texture))


    def _rotary_handler(self, direction, pressed):
        try:
            self.current_screen.on_rotary_turn(direction, pressed)
        except AttributeError:
            PIHOME_LOGGER.error("No on_rotary_turn method found in current screen")

    def _rotary_on_down(self):
        try:
            if not self.current_screen.disable_rotary_press_animation:
                PULSER.burst()
            self.current_screen.on_rotary_down()
        except AttributeError:
            PIHOME_LOGGER.error("No on_rotary_down method found in current screen")

    def _rotary_pressed(self, long_press = False):
        try:
            if long_press is True:
                self.current_screen.on_rotary_long_pressed()
            else:
                self.current_screen.on_rotary_pressed()
        except AttributeError:
            PIHOME_LOGGER.error("No on_rotary_pressed method found in current screen")
    
    def reload_all(self):
        PIHOME_LOGGER.info("Reloading all screens")
        for screen in self.screens:
            screen.on_config_update(CONFIG)
        

    def goto(self, screen_name, pin_verified = False):
        # make sure screen isn't locked (and that there is a current screen)
        if self.current_screen and self.current_screen.locked:
            PIHOME_LOGGER.info("Screen is locked, cannot change screens.")
            return

        # if self.transition.direction == "up":
        #     self.transition.direction = "down"
        # else:
        #     self.transition.direction = "up"
        
        if self.loaded_screens[screen_name].requires_pin and not pin_verified:
            def unlock_screen():
                self.current_screen.locked = False
                self.goto(screen_name, True)
            pinpad = PinPad(on_enter=unlock_screen)
            self.current_screen.add_widget(pinpad)
            pinpad.show()

            # Prevent the screen from changing until pin is verified
            self.current_screen.locked = True
        else:
            self.current = screen_name

        ### TODO Add pin check here - replace goto_screen in main.py
        # self.current = screen_name

    def on_parent(self, base_widget, parent):
        # Add the app menu to the parent of the screen manager
        self.load_screens()

        # Create an App Menu for the screens
        from composites.AppMenu.appmenu import AppMenu
        self.app_menu = AppMenu(self.loaded_screens)
        # We have to wait a second before adding the app menu to the parent becuase if we don't
        # the app menu will be added to the parent before the screen manager is added to the parent
        Clock.schedule_once(lambda dt: parent.add_widget(self.app_menu, index=1), 1)
        Clock.schedule_once(lambda dt: parent.add_widget(PULSER), 2)


    def load_screens(self):
        """
        This function will load all screens into the screen manager dynamically.  It does this by searching 
        through all subdirectories of the ./screens/ directory and looking for a 'manifest.json' file.  The manifest
        will have metadata about the screen such as the name, the class, and the icon.  This function will then 
        load the screen into the screen manager.
        """
        if self.screens_loaded:
            return
        screen_dir = "./screens/"
        for root, dirs, files in os.walk(screen_dir):
            for file in files:
                if file == "manifest.json":
                    with open(os.path.join(root, file), "r") as manifest:
                        # read the manifest file
                        metadata = json.load(manifest)
                        # load the screen
                        screen_module = metadata["module"]
                        screen_label = metadata["label"]
                        screen_name = metadata["name"]
                        screen_id = metadata["id"]
                        screen_hidden = metadata["hidden"]
                        screen_requires_pin = metadata["requires_pin"]
                        screen_icon = None
                        if "icon" in metadata:
                            screen_icon = metadata["icon"]

                        # if there is an index, use it
                        if "index" in metadata:
                            index = metadata["index"]
                        else:
                            index = 9999

                        # ensure the screen is not disabled
                        if "disabled" in metadata and metadata["disabled"]:
                            continue

                        # dynamically import the class from the module
                        module = __import__("screens.{}".format(screen_module), fromlist=[screen_module])
                        screen = getattr(module, screen_name)(name=screen_id, label=screen_label, is_hidden=screen_hidden, requires_pin=screen_requires_pin)
                        screen.app_index = index
                        if screen_icon:
                            screen.icon = screen_icon
                        self.add_widget(screen)
                        self.loaded_screens[screen_id] = screen
                        PIHOME_LOGGER.info("[ PihomeScreenManager ] Loaded screen: {}".format(screen_id))
        # sort the screens by their index
        self.loaded_screens = {k: v for k, v in sorted(self.loaded_screens.items(), key=lambda item: item[1].app_index)}


        # goto the first screen in the loaded screens list
        self.goto(list(self.loaded_screens.keys())[0])
        self.screens_loaded = True

        
PIHOME_SCREEN_MANAGER = PiHomeScreenManager(transition=NoTransition())