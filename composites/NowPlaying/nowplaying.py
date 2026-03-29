"""Now Playing card widget — displays AirPlay track metadata and album art."""

from io import BytesIO

from kivy.lang import Builder
from kivy.uix.widget import Widget
from kivy.properties import (
    StringProperty, ObjectProperty, ColorProperty,
)
from kivy.core.image import Image as CoreImage

from theme.theme import Theme
from util.phlog import PIHOME_LOGGER

Builder.load_file("./composites/NowPlaying/nowplaying.kv")

_theme = Theme()


class NowPlayingWidget(Widget):
    """Horizontal card showing album art + title/artist/album."""

    track_title = StringProperty("Unknown Title")
    track_artist = StringProperty("Unknown Artist")
    track_album = StringProperty("")
    art_texture = ObjectProperty(None, allownone=True)

    # Theme colors
    text_color = ColorProperty(_theme.get_color(_theme.TEXT_PRIMARY))
    muted_color = ColorProperty(_theme.get_color(_theme.TEXT_SECONDARY))
    album_color = ColorProperty([1, 1, 1, 0.3])
    card_color = ColorProperty([0.10, 0.10, 0.14, 0.85])
    art_bg_color = ColorProperty([1, 1, 1, 0.06])

    def update_data(self, airplay):
        """Update widget from an AirPlay service instance."""
        self.track_title = airplay.title or "Unknown Title"
        self.track_artist = airplay.artist or "Unknown Artist"
        self.track_album = airplay.album or ""

    def set_cover_art(self, raw_bytes):
        """Convert raw image bytes to a Kivy Texture."""
        if not raw_bytes:
            self.art_texture = None
            return
        buf = None
        try:
            buf = BytesIO(raw_bytes)
            core_img = CoreImage(buf, ext="jpg")
            self.art_texture = core_img.texture
        except Exception as e:
            PIHOME_LOGGER.error("NowPlaying: cover art decode failed: {}".format(e))
            self.art_texture = None
        finally:
            if buf:
                buf.close()

    def update_theme(self):
        """Refresh colors from the current theme."""
        th = Theme()
        self.text_color = th.get_color(th.TEXT_PRIMARY)
        self.muted_color = th.get_color(th.TEXT_SECONDARY)
        self.album_color = list(th.get_color(th.TEXT_SECONDARY))[:3] + [0.3]
        bg = th.get_color(th.BACKGROUND_SECONDARY)
        self.card_color = list(bg)[:3] + [0.85]
        self.art_bg_color = list(th.get_color(th.TEXT_PRIMARY))[:3] + [0.06]
