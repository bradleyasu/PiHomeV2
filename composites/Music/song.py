from kivy.lang import Builder
from components.Image.networkimage import BLANK_IMAGE
from interface.gesturewidget import GestureWidget
from services.audio.audioplayer import AUDIO_PLAYER
from services.qr.qr import QR
from theme.color import Color
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.animation import Animation
from kivy.clock import Clock
from util.const import GESTURE_SWIPE_DOWN

Builder.load_file("./composites/Music/song.kv")

class Song(GestureWidget):

    theme = Theme()
    background_color = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY, 0.2))
    active_color = ColorProperty(Color.CELERY_700)
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    text_color_secondary = ColorProperty(theme.get_color(theme.TEXT_SECONDARY))

    index = NumericProperty(0)
    title = StringProperty("Unknown")
    url = StringProperty("Unknown")
    active = BooleanProperty(False)

    def __init__(self, index = 0, title = "Unknown", url = "Unknown", **kwargs):
        super(Song, self).__init__(**kwargs)
        self.index = index;
        self.title = title
        self.url = url
        self.on_click = self.handle_click
        Clock.schedule_interval(lambda _: self._run(), 1)


    def handle_click(self):
        AUDIO_PLAYER.playlist_play_index(self.index)
    
    def _run(self):
        if AUDIO_PLAYER.playlist_pos == self.index:
            self.active = True
        else:
            self.active = False
