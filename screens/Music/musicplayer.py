import json
import subprocess
from composites.Music.song import Song
from composites.Music.volume import Volume
from composites.Reddit.redditwidget import RedditWidget
import requests
import time
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty, NumericProperty, ListProperty

from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.SmartLight.smartlight import SmartLight
from composites.Weather.weatherwidget import WeatherWidget
from interface.pihomescreen import PiHomeScreen
from services.albumart.albumart import AlbumArtFactory
from services.qr.qr import QR
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import appmenu_open, audio_player, get_app, goto_screen, local_ip, weather
from util.tools import hex
from kivy.clock import Clock
from kivy.animation import Animation
from util.const import _SETTINGS_SCREEN, CDN_ASSET, GESTURE_SWIPE_DOWN, SERVER_PORT

Builder.load_file("./screens/Music/musicplayer.kv")


ICO_PLAY = "./assets/icons/audio_play.png"
ICO_PAUSE = "./assets/icons/audio_pause.png"
ICO_STOP = "./assets/icons/audio_stop.png"
ICO_NEXT = "./assets/icons/audio_next.png"
ICO_LAST = "./assets/icons/audio_last.png"
ICO_VOLUME = "./assets/icons/audio_volume.png"
ICO_MUTE = "./assets/icons/audio_mute.png"
ART = "./assets/images/audio_vinyl.png"
class MusicPlayer(PiHomeScreen):
    theme = Theme()
    text_color = ColorProperty(theme.get_color(theme.TEXT_PRIMARY))
    background_color_prime = ColorProperty(theme.get_color(theme.BACKGROUND_PRIMARY, 0.4))
    background_color_secondary = ColorProperty(theme.get_color(theme.BACKGROUND_SECONDARY, 0.4))

    track_color = ColorProperty(Color.DARK_GRAY_700)
    track_prog_color = ColorProperty(Color.CELERY_700)

    album_art = StringProperty(ART)
    next_btn = StringProperty(ICO_NEXT)
    last_btn = StringProperty(ICO_LAST)
    play_control_btn = StringProperty(ICO_PLAY)

    percent = NumericProperty(0)
    media_name = StringProperty("No Media")
    volume_level = NumericProperty(100)
    queue = ListProperty([])

    expand_offset = NumericProperty(0)

    queue_open = False

    def __init__(self, **kwargs):
        super(MusicPlayer, self).__init__(**kwargs)
        self.icon = CDN_ASSET.format("music_icon.png")

        self.qr = QR().from_url("http://{}:{}".format(local_ip(), SERVER_PORT))
        Clock.schedule_interval(lambda _: self._run(), 0.1)
        self.grid = self.ids["audio_playlist"]
        self.aa_factory = AlbumArtFactory()
        self.grid.bind(minimum_height=self.grid.setter('height'))

    # def on_album_art(self, instance, value):
        # self.icon = value

    def on_queue(self, instance, value):
        self.grid.clear_widgets()
        index = 0
        for i in value:
            title = "Unknown"
            url = "--"
            if "title" in i:
                title = i["title"]
            if "id" in i:
                index = int(i["id"])
            if "filename" in i:
                url = i["filename"]
            song = Song(index, title, url)
            self.grid.add_widget(song)
            index = index + 1

    def toggle_play(self, widget, touch):
        if widget.collide_point(*touch.pos):
            audio_player().toggle_play()
            return False

    def next(self, widget, touch):
        if widget.collide_point(*touch.pos):
            audio_player().next()
            return False

    def prev(self, widget, touch):
        if widget.collide_point(*touch.pos):
            audio_player().prev()
            return False

    def toggle_queue(self, widget, touch):
        if widget.collide_point(*touch.pos):
            offset = 300
            if self.queue_open:
                offset = 0
            animation = Animation(expand_offset=offset, t='out_bounce', d=0.250)
            animation.start(self)
            self.queue_open = not self.queue_open
        return False
        
    def _run(self):
        name_change = not (self.media_name == audio_player().title)
        self.media_name = audio_player().title
        self.percent = audio_player().percent
        self.volume_level = audio_player().volume
        self.queue = audio_player().queue
        if audio_player().is_playing:
            self.play_control_btn = ICO_PAUSE
        else:
            self.play_control_btn = ICO_PLAY
            # self.album_art = self.qr
        
        if name_change and self.media_name != "No Media":
            self.aa_factory.find(self.media_name, self.parse_album_art)
        
    def parse_album_art(self, json):
        if "results" in json and len(json["results"]) > 0:
            self.album_art = json["results"][0]["cover_image"]
        else:
            self.album_art = ART