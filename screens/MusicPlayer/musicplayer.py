from interface.pihomescreen import PiHomeScreen
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.graphics import RenderContext
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty, NumericProperty
from kivy.graphics.texture import Texture
import numpy as np
from services.audio.audioplayernew import AUDIO_PLAYER
from kivy.uix.floatlayout import FloatLayout
from screens.MusicPlayer.shaders import sVINYL
from kivy.graphics import BindTexture

Builder.load_file("./screens/MusicPlayer/musicplayer.kv")
class MusicPlayerContainer(PiHomeScreen):
    sound = None
    def __init__(self, **kwargs):
        super(MusicPlayerContainer, self).__init__(**kwargs)
        self.add_widget(MusicPlayerCard())

    
    def on_enter(self, *args):
        # AUDIO_PLAYER.play("https://manifest.googlevideo.com/api/manifest/hls_playlist/expire/1709846169/ei/OdrpZYrjNsye_9EP_8ORQA/ip/74.109.241.148/id/AS_x4uR87Kw.1/itag/234/source/yt_live_broadcast/requiressl/yes/ratebypass/yes/live/1/goi/133/sgoap/gir%3Dyes%3Bitag%3D140/rqh/1/hls_chunk_host/rr1---sn-8xgp1vo-2pue.googlevideo.com/xpc/EgVo2aDSNQ%3D%3D/playlist_duration/3600/manifest_duration/3600/vprv/1/playlist_type/DVR/initcwndbps/862500/mh/Op/mm/44/mn/sn-8xgp1vo-2pue/ms/lva/mv/m/mvi/1/pl/18/dover/13/pacing/0/short_key/1/keepalive/yes/fexp/24007246/mt/1709823871/sparams/expire,ei,ip,id,itag,source,requiressl,ratebypass,live,goi,sgoap,rqh,xpc,playlist_duration,manifest_duration,vprv,playlist_type/sig/AJfQdSswRQIhAPSwLvJ6OrqrT5Zxu7ktZWLRK_e2I026V1RvpJwfBxT6AiBINrL9NSqzMDMeqMLpObGdXErxWkK4S6sObzZXrpB2GA%3D%3D/lsparams/hls_chunk_host,initcwndbps,mh,mm,mn,ms,mv,mvi,pl/lsig/APTiJQcwRQIgeG5uTx_82kPVQrpyzEcSH7wJEp-Ix7UXK6lqvWUCTCgCIQCkp-KOzU1Uam9qbmTcpsAnluyTjDy9MTdhcZsNWbjrIw%3D%3D/playlist/index.m3u8")

        # AUDIO_PLAYER.play("https://cf-media.sndcdn.com/0OjHiwy9wqQK.128.mp3?Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiKjovL2NmLW1lZGlhLnNuZGNkbi5jb20vME9qSGl3eTl3cVFLLjEyOC5tcDMqIiwiQ29uZGl0aW9uIjp7IkRhdGVMZXNzVGhhbiI6eyJBV1M6RXBvY2hUaW1lIjoxNzA5ODMwMDU0fX19XX0_&Signature=ZSW0AyWO1ayG6RgouLWd1Di-3-WRcAkx7zAEBcbu2h6Enwzz5z-SI7bJcRF7mA5DwqVSSCQKak5HgV5BZeDCwEHtzw6MN-sKVUCGBv-7Ei~DXhIVcAEBh~AftaY0jadvtvEu1RU~S9x8hDbt4mE810fa9sK2guFYHF8bj9cE625VMW6UAc~E7MLOkB48Io7ORv9CPrsBlkuH21d-PjCFka8b98tK119txs5u-IlU5zP0ECsfnI700pXikNjapYHckJpXPnWCTkvyRyyvp70kQIJmq4-cVYWPOPu8cNadG91LpGLrwe4vtANTg0xu2FkWfWZyBrdwtdvccTW4t412Tg__&Key-Pair-Id=APKAI6TU7MMXM5DG6EPQ")

        AUDIO_PLAYER.play("/Users/bradsheets/Projects/pihome/services/audio/test.mp3")


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
        
        self.vinyl = VinylWidget(fs=sVINYL)
        self.vinyl.xOffset = 2.2
        self.vinyl.yOffset = 0.25
        self.add_widget(self.vinyl)
        
class PlayerQueue(BoxLayout):
    def __init__(self, **kwargs):
        super(PlayerQueue, self).__init__(**kwargs)


class VinylWidget(FloatLayout):
    fs = StringProperty(None)
    sound = None
    audio_texture = ObjectProperty(None)
    xOffset = NumericProperty(0) 
    yOffset = NumericProperty(0)

    def __init__(self, **kwargs):
        self.canvas = RenderContext(
            use_parent_projection=True,
            use_parent_modelview=True,
            use_parent_frag_modelview=False
        )
        super(VinylWidget, self).__init__(**kwargs)
        Clock.schedule_interval(self.update_glsl, 1 / 60.)
        self.audio_texture = Texture.create(size=(AUDIO_PLAYER.buffersize, 2), colorfmt='luminance')
        with self.canvas:
            # Bind the custom texture at index 1, which will be texture1 in the shader
            # texture0 seems to be special for kivy, so we use texture1
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
        # self.canvas['offsetX'] = 1.7 # Left side 
        # self.canvas['offsetX'] = 2.2
        # self.canvas['offsetY'] = 0.25
        self.canvas['offsetX'] = self.xOffset
        self.canvas['offsetY'] = self.yOffset

        if AUDIO_PLAYER.data:
            # Update the audio texture with new data
            audio_data = AUDIO_PLAYER.data
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            # audio_array = self.normalize_data(audio_array)
            audio_bytes = audio_array.tobytes()
            self.audio_texture.blit_buffer(audio_bytes, colorfmt='luminance', bufferfmt='float')
        else:
            audio_data = np.zeros(AUDIO_PLAYER.buffersize, dtype=np.float32).tobytes()
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
        self.canvas['texture1'] = 1 # Set to texture unit 0
        self.canvas.ask_update()

    def set_center_x(self, value):
        return super().set_center_x(value)

    def set_sound(self, sound):
        self.sound = sound
