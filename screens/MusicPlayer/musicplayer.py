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
from kivy.uix.slider import Slider
from datetime import datetime
from kivy.uix.gridlayout import GridLayout
from components.Button.circlebutton import CircleButton

Builder.load_file("./screens/MusicPlayer/musicplayer.kv")
class MusicPlayerContainer(PiHomeScreen):
    sound = None
    current_time = StringProperty("00:00 PM")
    def __init__(self, **kwargs):
        super(MusicPlayerContainer, self).__init__(**kwargs)
        self.add_widget(MusicPlayerCard())

        Clock.schedule_interval(lambda _: self.update_current_time(), 1)

    def on_enter(self, *args):
        return super().on_enter(*args)

    def on_leave(self, *args):
        if self.sound:
            self.sound.stop()
            self.sound.unload()
        return super().on_leave(*args)
    
    def update_current_time(self):
        now = datetime.now()
        self.current_time = now.strftime("%I:%M %p")


class MusicPlayerCard(BoxLayout):
    def __init__(self, **kwargs):
        super(MusicPlayerCard, self).__init__(**kwargs)
        self.add_widget(Player())

class Player(BoxLayout):
    def __init__(self, **kwargs):
        super(Player, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        
        self.vinyl = VinylWidget(fs=sVINYL)
        self.vinyl.xOffset = 2.35
        self.vinyl.yOffset = 0.81
        self.vinyl.size_hint = (1, 1)
        self.vinyl.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        self.add_widget(self.vinyl)

        player_grid = GridLayout(rows=2)
        s = Slider(min=0, max=1, value=1, step=0.01)
        s.bind(value=lambda _, v:AUDIO_PLAYER.set_volume(v))
        player_grid.add_widget(s)

        def set_volume(v):
            s.value = v
        AUDIO_PLAYER.add_volume_listener(lambda v: set_volume(v))


        buttons = BoxLayout(orientation='horizontal')

        stop = CircleButton(text="STOP")
        stop.bind(on_release=lambda _: AUDIO_PLAYER.stop())
        stop.font_size = 10
        stop.stroke_color = (0, 0, 0, 0)
        stop.text_color = (0, 0, 0, 1)

        play= CircleButton(text="PLAY")
        play.bind(on_release=lambda _: AUDIO_PLAYER.play("/Users/bradsheets/Projects/pihome/services/audio/test_file.mp3"))
        play.font_size = 10
        play.stroke_color = (0, 0, 0, 0)
        play.text_color = (0, 0, 0, 1)


        buttons.add_widget(play)
        buttons.add_widget(stop)

        player_grid.add_widget(buttons)

        self.add_widget(player_grid)
        
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
        self.canvas['volume'] = AUDIO_PLAYER.volume

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
