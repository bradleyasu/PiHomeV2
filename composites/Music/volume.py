from kivy.lang import Builder
from components.Image.networkimage import BLANK_IMAGE
from interface.gesturewidget import GestureWidget
from services.audio.audioplayernew import AUDIO_PLAYER
from services.qr.qr import QR
from theme.color import Color
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.animation import Animation
from kivy.clock import Clock
from util.const import GESTURE_SWIPE_DOWN
from util.tools import hex

Builder.load_file("./composites/Music/volume.kv")

class Volume(GestureWidget):

    theme = Theme()
    background_color = ColorProperty(hex(Color.DARK_SEAFOAM_700, 0.1))
    active_color = ColorProperty(Color.DARK_SEAFOAM_700)
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    text_color_secondary = ColorProperty(theme.get_color(theme.TEXT_SECONDARY))


    level = NumericProperty(100)
    touching = False

    def __init__(self, **kwargs):
        super(Volume, self).__init__(**kwargs)
        Clock.schedule_interval(lambda _: self._run(), 1)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            height = (self.height)
            position = (touch.y - self.y)
            self.level = position/height * 100.0
            AUDIO_PLAYER.set_volume(self.level)
        return False
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.touching = True

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            self.touching = False
    
    def _run(self):
        if not self.touching:
            self.level = AUDIO_PLAYER.volume
