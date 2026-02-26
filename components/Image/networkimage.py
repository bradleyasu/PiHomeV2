import os
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import AsyncImage  
from kivy.uix.label import Label
from theme.theme import Theme
from kivy.properties import ColorProperty, BooleanProperty, NumericProperty, StringProperty, ObjectProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.loader import Loader
from kivy.metrics import dp
from kivy.graphics import Rectangle, Color
from kivy.core.image import Image as CoreImage

BLANK_IMAGE = "./assets/images/blank.png"
LOGO_IMAGE = "./assets/images/pihome_logo_white.png"

class NetworkImage(Widget):
    theme = Theme()

    color = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY))
    url = StringProperty()
    prev_image = ""
    stretch = BooleanProperty(False)
    k_ratio = BooleanProperty(True)
    loader = None
    error = None
    _texture = ObjectProperty(None, allownone=True)
    _rectangle = ObjectProperty(None, allownone=True)
    _proxyimage = ObjectProperty(None, allownone=True)

    auto_refresh_interval = NumericProperty(0)

    def __init__(self, url = "", size=(dp(50), dp(50)), pos=(dp(10), dp(10)), enable_stretch = False, loader = None, error = None, **kwargs):
        super(NetworkImage, self).__init__(**kwargs)
        Loader.loading_image = BLANK_IMAGE
    
        self.size = size
        self.pos = pos
        self.stretch = enable_stretch
        self.k_ratio = not enable_stretch
        self.loader = loader
        self.error = error
        
        # Setup canvas rendering
        with self.canvas:
            self._color = Color(1, 1, 1, 1)
            self._rectangle = Rectangle(pos=self.pos, size=self.size)
        
        self.bind(pos=self._update_rect, size=self._update_rect)
        
        if self.auto_refresh_interval > 0:
            Clock.schedule_interval(lambda _: self.reload(), self.auto_refresh_interval)
        
        # Set URL last to trigger loading
        self.url = url
        

    def _update_rect(self, *args):
        if self._rectangle:
            self._rectangle.pos = self.pos
            self._rectangle.size = self.size
            self._update_texture_coords()
    
    def _update_texture_coords(self):
        if not self._rectangle or not self._texture:
            return
        
        if self.stretch:
            # Stretch to fill
            self._rectangle.texture = self._texture
        elif self.k_ratio and self._texture:
            # Keep aspect ratio
            self._rectangle.texture = self._texture
            # Calculate size to maintain aspect ratio
            aspect = self._texture.width / float(self._texture.height)
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
            self._rectangle.size = (new_width, new_height)
            self._rectangle.pos = (
                self.x + (self.width - new_width) / 2,
                self.y + (self.height - new_height) / 2
            )
        else:
            self._rectangle.texture = self._texture
    
    def on_url(self, instance, value):
        if not value:
            return
        
        # Load image asynchronously
        if self._proxyimage:
            # Remove old image from cache
            Loader.image(self._proxyimage.url).remove_from_cache()
        
        self._proxyimage = Loader.image(value, nocache=False)
        self._proxyimage.bind(on_load=self._on_image_load, on_error=self._on_image_error)
    
    def _on_image_load(self, proxyimage):
        self._texture = proxyimage.texture
        if self._rectangle:
            self._rectangle.texture = self._texture
            self._update_texture_coords()
        self.on_load()
    
    def _on_image_error(self, proxyimage):
        self.on_error()
        if self.error:
            self.url = self.error

    def set_stretch(self, enable_stretch):
        self.stretch = enable_stretch
        self.k_ratio = not enable_stretch
        self._update_texture_coords()

    def reload(self):
        if self.url:
            # Clear from cache and reload
            try:
                Loader.image(self.url).remove_from_cache()
            except:
                pass
            # Trigger reload by re-setting URL
            url = self.url
            self.url = ""
            self.url = url

    def on_error(self, a = None, b = None):
        pass
    
    def on_load(self):
        pass

    def on_auto_refresh_interval(self, instance, value):
        if value > 0:
            Clock.schedule_interval(lambda _: self.reload(), value)


