


from kivy.uix.widget import Widget

from interface.pihomescreen import PiHomeScreen
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.graphics import RenderContext
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import StringProperty, ObjectProperty
from kivy.core.audio import SoundLoader
from kivy.graphics.texture import Texture
import numpy as np
from kivy.graphics.opengl import glBindTexture, GL_TEXTURE_2D, GL_TEXTURE9, glActiveTexture, GL_TEXTURE0, glUniform1i, glGetError, glUseProgram, GL_LINEAR, GL_CLAMP_TO_EDGE, glTexParameteri, GL_TEXTURE1,GL_TEXTURE3, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T
from services.audio.audioplayernew import AUDIO_PLAYER
from kivy.uix.floatlayout import FloatLayout
from screens.MusicPlayer.shaders import sVINYL
from kivy.graphics import BindTexture

Builder.load_file("./screens/MusicPlayer/musicplayer.kv")
class MusicPlayerContainer(PiHomeScreen):
    sound = None
    def __init__(self, **kwargs):
        super(MusicPlayerContainer, self).__init__(**kwargs)
        self.vinyl = VinylWidget(fs=sVINYL)
        self.add_widget(self.vinyl)
        self.add_widget(MusicPlayerCard())

    
    def on_enter(self, *args):
        # url = "https://rr3---sn-8xgp1vo-2pul.googlevideo.com/videoplayback?expire=1709337780&ei=VBjiZdeJFeG9_9EP3J2AiA8&ip=74.109.241.148&id=o-ALLuUo5hmYuUdLSWnmmfJedi9hpY8h8b58OCsN-HQCpc&itag=251&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&mh=Nn&mm=31%2C29&mn=sn-8xgp1vo-2pul%2Csn-8xgp1vo-p5qe&ms=au%2Crdu&mv=m&mvi=3&pl=18&gcr=us&initcwndbps=898750&spc=UWF9fzggasD4niyPJNKYKiVzKvYnUtZ3cbXFjsryDK4EqWs&vprv=1&svpuc=1&mime=audio%2Fwebm&gir=yes&clen=4391306&dur=278.361&lmt=1706308899802101&mt=1709315833&fvip=6&keepalive=yes&fexp=24007246&c=ANDROID&txp=4532434&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cgcr%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Cgir%2Cclen%2Cdur%2Clmt&sig=AJfQdSswRQIgQE0R0uwDzqSxnuX_9B5vtfx8_LsUlvvH__bxjLVujp0CIQCqe4oUM7hOdBOkc0gk2h60UCK-yyZZWEr08oao6fIMpw%3D%3D&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Cinitcwndbps&lsig=APTiJQcwRgIhAPaaWdV0tV5FkPYOpHN82ZKBLn27S6Dc79TMTJQigrf4AiEAq5jcfnMox5ToATXrgG4QcMyMGSUSgOOlA7yI06Rp0nY%3D&fmt=.mp3"
        # self.sound = SoundLoader.load(url)
        # self.sound.play()

        # get audio texture for vinyl shader
        # self.vinyl.set_sound(self.sound)
        AUDIO_PLAYER.play("https://manifest.googlevideo.com/api/manifest/hls_playlist/expire/1709846169/ei/OdrpZYrjNsye_9EP_8ORQA/ip/74.109.241.148/id/AS_x4uR87Kw.1/itag/234/source/yt_live_broadcast/requiressl/yes/ratebypass/yes/live/1/goi/133/sgoap/gir%3Dyes%3Bitag%3D140/rqh/1/hls_chunk_host/rr1---sn-8xgp1vo-2pue.googlevideo.com/xpc/EgVo2aDSNQ%3D%3D/playlist_duration/3600/manifest_duration/3600/vprv/1/playlist_type/DVR/initcwndbps/862500/mh/Op/mm/44/mn/sn-8xgp1vo-2pue/ms/lva/mv/m/mvi/1/pl/18/dover/13/pacing/0/short_key/1/keepalive/yes/fexp/24007246/mt/1709823871/sparams/expire,ei,ip,id,itag,source,requiressl,ratebypass,live,goi,sgoap,rqh,xpc,playlist_duration,manifest_duration,vprv,playlist_type/sig/AJfQdSswRQIhAPSwLvJ6OrqrT5Zxu7ktZWLRK_e2I026V1RvpJwfBxT6AiBINrL9NSqzMDMeqMLpObGdXErxWkK4S6sObzZXrpB2GA%3D%3D/lsparams/hls_chunk_host,initcwndbps,mh,mm,mn,ms,mv,mvi,pl/lsig/APTiJQcwRQIgeG5uTx_82kPVQrpyzEcSH7wJEp-Ix7UXK6lqvWUCTCgCIQCkp-KOzU1Uam9qbmTcpsAnluyTjDy9MTdhcZsNWbjrIw%3D%3D/playlist/index.m3u8")


        return super().on_enter(*args)

    def on_leave(self, *args):
        if self.sound:
            self.sound.stop()
            self.sound.unload()
        return super().on_leave(*args)


class MusicPlayerCard(BoxLayout):
    def __init__(self, **kwargs):
        super(MusicPlayerCard, self).__init__(**kwargs)
        self.add_widget(Player())

class Player(BoxLayout):
    def __init__(self, **kwargs):
        super(Player, self).__init__(**kwargs)
        
class PlayerQueue(BoxLayout):
    def __init__(self, **kwargs):
        super(PlayerQueue, self).__init__(**kwargs)


class VinylWidget(FloatLayout):
    fs = StringProperty(None)
    sound = None
    audio_texture = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.canvas = RenderContext(
            use_parent_projection=True,
            use_parent_modelview=True,
            use_parent_frag_modelview=False
        )
        super(VinylWidget, self).__init__(**kwargs)
        Clock.schedule_interval(self.update_glsl, 1 / 60.)
        # self.audio_texture = self.create_texture((512, 1))
        self.audio_texture = Texture.create(size=(1, 512), colorfmt='luminance')

        with self.canvas:
            BindTexture(texture=self.audio_texture, index=1)

    def on_fs(self, instance, value):
        shader = self.canvas.shader
        old_value = shader.fs
        shader.fs = value
        if not shader.success:
            shader.fs = old_value
            raise Exception('Shader compilation failed')

    def update_glsl(self, *largs):
        self.canvas['time'] = Clock.get_boottime()
        self.canvas['resolution'] = list(map(float, self.size))

        if AUDIO_PLAYER.data:
            # Update the audio texture with new data
            audio_data = AUDIO_PLAYER.data
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            # audio_array = self.normalize_data(audio_array)
            audio_bytes = audio_array.tobytes()
            self.audio_texture.blit_buffer(audio_bytes, colorfmt='luminance', bufferfmt='float')
        else:
            audio_data = np.zeros(512, dtype=np.float32).tobytes()
            self.audio_texture.blit_buffer(audio_data, colorfmt='luminance', bufferfmt='float')
        
        self.set_channel()
        
    def bytes_to_texture(self, audio_data):
        audio_array = np.frombuffer(audio_data, dtype=np.float32)
        audio_array = self.normalize_data(audio_array)
        audio_bytes = audio_array.tobytes()
        texture_size = (1, len(audio_array))
        texture = Texture.create(size=texture_size, colorfmt='luminance')
        texture.blit_buffer(audio_bytes, colorfmt='luminance', bufferfmt='float')
        return texture

    def normalize_data(self, data):
        min_val = np.min(data)
        max_val = np.max(data)
        if max_val == min_val:
            return data
        return (data - min_val) / (max_val - min_val)

    def create_texture(self, size):
        return np.zeros(size)

    def set_channel(self):
        self.audio_texture.bind()
        # glActiveTexture(GL_TEXTURE0)
        # glBindTexture(GL_TEXTURE_2D, self.audio_texture.id)
        # self.canvas['audioTexture'] = 0 # Set to texture unit 0
        self.canvas['texture1'] = 1 # Set to texture unit 0
        self.canvas.ask_update()
        # glBindTexture(GL_TEXTURE_2D, 0)

    def set_center_x(self, value):
        return super().set_center_x(value)

    def set_sound(self, sound):
        self.sound = sound
