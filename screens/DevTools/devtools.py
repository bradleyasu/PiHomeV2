import socket
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty, NumericProperty

from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.SmartLight.smartlight import SmartLight
from components.Switch.switch import PiHomeSwitch
from interface.pihomescreen import PiHomeScreen
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.helpers import appmenu_open, get_app, goto_screen, update_pihome
from util.tools import hex
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.uix.slider import Slider
from kivy.uix.label import Label
from kivy.uix.videoplayer import VideoPlayer

from kivy.core.audio import SoundLoader

Builder.load_file("./screens/DevTools/devtools.kv")

class DevTools(PiHomeScreen):
    local_ip = StringProperty("0.0.0.0")
    theme = Theme()
    slider = None
    def __init__(self, **kwargs):
        super(DevTools, self).__init__(**kwargs)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        self.local_ip = s.getsockname()[0]
        s.close()
        self.build()

    
    def build(self):
        layout = FloatLayout(size=(dp(800), dp(600)))

        button = CircleButton(text='X', size=(dp(50), dp(50)), pos=(dp(self.width - 70), dp(self.height - 200)))
        button.stroke_color = self.theme.get_color(self.theme.ALERT_DANGER)
        button.text_color = self.theme.get_color(self.theme.ALERT_DANGER)
        button.down_color = self.theme.get_color(self.theme.ALERT_DANGER, 0.2)
        button.bind(on_release=lambda _: update_pihome())
        layout.add_widget(button)


        stopbutton = CircleButton(text='>', size=(dp(50), dp(50)), pos=(dp(20), dp(self.height - 200)))
        stopbutton.stroke_color = self.theme.get_color(self.theme.ALERT_SUCCESS)
        stopbutton.text_color = self.theme.get_color(self.theme.ALERT_SUCCESS)
        stopbutton.down_color = self.theme.get_color(self.theme.ALERT_SUCCESS, 0.2)
        stopbutton.bind(on_release=lambda _: self.play_sound())
        layout.add_widget(stopbutton)

        switch = PiHomeSwitch(pos=(dp(20), dp(20)))
        layout.add_widget(switch)

        self.sound = SoundLoader.load('./assets/audio/notify/001.wav')


        # url = "https://manifest.googlevideo.com/api/manifest/hls_playlist/expire/1660699899/ei/m_D7YuynC--G_9EP2PGJWA/ip/2600:4041:2d6:6000:81b:726d:82a3:8bb/id/jfKfPfyJRdk.1/itag/96/source/yt_live_broadcast/requiressl/yes/ratebypass/yes/live/1/sgoap/gir%3Dyes%3Bitag%3D140/sgovp/gir%3Dyes%3Bitag%3D137/hls_chunk_host/rr3---sn-8xgp1vo-2pue.googlevideo.com/playlist_duration/30/manifest_duration/30/spc/lT-KhiLi3CN23K3TDpfX3r4WvA7PNGc/vprv/1/playlist_type/DVR/initcwndbps/1356250/mh/rr/mm/44/mn/sn-8xgp1vo-2pue/ms/lva/mv/m/mvi/3/pl/36/dover/11/pacing/0/keepalive/yes/fexp/24001373,24007246/mt/1660677877/sparams/expire,ei,ip,id,itag,source,requiressl,ratebypass,live,sgoap,sgovp,playlist_duration,manifest_duration,spc,vprv,playlist_type/sig/AOq0QJ8wRQIgKiPCI-g6rbFgY7p9-b76hDO9nOSKKAVDZBM3EouRYI0CIQD9BZ5JJ1ZaEmtOTRX2sME7LO31JcU9W-HGXdJGkHXj2Q%3D%3D/lsparams/hls_chunk_host,initcwndbps,mh,mm,mn,ms,mv,mvi,pl/lsig/AG3C_xAwRQIhAP1qcayhbCW4-mqCFp7O3XpT48YmZ0-aiI16FXg4-PVFAiAK5PhJDsQNFdXdLynNjKAL-n8lCzGyjNNszcFZaPS-Ew%3D%3D/playlist/index.m3u8"
        # player = VideoPlayer(source=url, state='play', options={'allow_stretch': True})

        # layout.add_widget(player)
        # self.slider = Slider(on_touch_move=lambda x,y: self.set_brightness(self.slider.value), orientation='horizontal', min=20, max = 255, pos=(dp(self.width - 10), dp(self.height - 100)), size=(dp(40), dp(200)), step=1)
        # layout.add_widget(self.slider)
        
        self.add_widget(layout)

    
    def set_brightness(self, level):
        # echo 32 > /sys/class/backlight/rpi_backlight/brightness
        # subprocess.call(['sh', './set_brightness.sh', level])
        print(level)

    def play_sound(self):
        if self.sound:
            self.sound.play()

  