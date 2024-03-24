from interface.pihomescreen import PiHomeScreen
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.graphics import RenderContext
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty, NumericProperty, ListProperty, BooleanProperty
from kivy.graphics.texture import Texture
import numpy as np
from kivy.uix.behaviors import ButtonBehavior
from services.audio.audioplayernew import AUDIO_PLAYER, AudioState
from kivy.uix.floatlayout import FloatLayout
from screens.MusicPlayer.shaders import sVINYL
from kivy.graphics import BindTexture
from kivy.uix.slider import Slider
from datetime import datetime
from kivy.uix.gridlayout import GridLayout
from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton

Builder.load_file("./screens/MusicPlayer/musicplayer.kv")
class MusicPlayerContainer(PiHomeScreen):
    sound = None
    current_time = StringProperty("00:00 PM")
    state = StringProperty("")
    def __init__(self, **kwargs):
        super(MusicPlayerContainer, self).__init__(**kwargs)
        self.add_widget(MusicPlayerCard(self.on_radio))
        self.drawer = RadioDrawer()
        self.add_widget(self.drawer)
        self.disable_rotary_press_animation = True

        Clock.schedule_interval(lambda _: self.update_current_time(), 1)
        AUDIO_PLAYER.add_state_listener(self.on_audio_state_change)

    def on_audio_state_change(self, state):
        if state == AudioState.FETCHING:
            self.state = "Fetching..."
        elif state == AudioState.BUFFERING:
            self.state = "Buffering..."
        elif state == AudioState.PLAYING:
            self.state = "Playing"
        else:
            self.state = ""

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

    def on_radio(self, *args):
        self.drawer.is_open = not self.drawer.is_open

    def on_rotary_down(self):
        if self.drawer.is_open:
            self.drawer.play_current()
        self.on_radio()

    def on_rotary_turn(self, direction, button_pressed):
        if self.drawer.is_open:
            if direction == -1:
                self.drawer.carousel_swipe_left()
            elif direction == 1:
                self.drawer.carousel_swipe_right()
        else:
            return super().on_rotary_turn(direction, button_pressed)

class RadioItem(ButtonBehavior, BoxLayout):
    text = StringProperty("")
    thumbnail = StringProperty("")
    url = StringProperty("")
    def __init__(self, text, url, thumbnail=None, **kwargs):
        super(RadioItem, self).__init__(**kwargs)
        # trim text to 12 characters
        if len(text) > 12:  
            text = text[:12] + "..."
        self.text = text
        self.url = url
        if thumbnail is not None and thumbnail != "":
            self.thumbnail = thumbnail
        else:
            self.thumbnail = "assets/images/audio_vinyl.png"

class RadioDrawer(BoxLayout):
    is_open = BooleanProperty(False)
    content = ListProperty([])

    def __init__(self, **kwargs):
        super(RadioDrawer, self).__init__(**kwargs)
        self.refresh()


    def on_is_open(self, *args):
        if self.is_open:
            self.content = AUDIO_PLAYER.saved_urls
            self.size_hint = (1, 0.4)
        else:
            self.size_hint = (1.0, 0.0)

    def on_content(self, *args):
        self.refresh()

    def refresh(self):
        carousel = self.ids["radio_carousel"]
        carousel.clear_widgets()
        for item in self.content:
            cover = RadioItem(text=item["text"], url=item["url"], thumbnail=item["thumbnail"], on_press=self.create_callback(item["url"]))
            cover.size_hint = (0.5, 0.5)
            cover.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
            carousel.add_widget(cover)

    def create_callback(self, url):
        return lambda *args: self.play_item(url)

    def play_item(self, url, *args):
        AUDIO_PLAYER.play(url)
        self.is_open = False

    def on_touch_down(self, touch):
        if self.is_open:
            if self.collide_point(*touch.pos):
                super().on_touch_down(touch)
                return True
            else:
                self.is_open = False
                return True
        return super().on_touch_down(touch)

    def play_current(self):
        # current widget in carousel
        selected = self.ids["radio_carousel"].current_slide
        self.play_item(selected.url)

    def carousel_swipe_left(self):
        self.ids["radio_carousel"].load_previous()

    def carousel_swipe_right(self):
        self.ids["radio_carousel"].load_next()
    

class MusicPlayerCard(BoxLayout):
    def __init__(self, on_radio, **kwargs):
        super(MusicPlayerCard, self).__init__(**kwargs)
        self.add_widget(Player(on_radio))

class Player(BoxLayout):
    def __init__(self, on_radio, **kwargs):
        super(Player, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        self.on_radio = on_radio
        
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
        stop.bind(on_release=lambda _: AUDIO_PLAYER.stop(clear_playlist=True))
        stop.font_size = '12sp'
        stop.stroke_color = (0, 0, 0, 0)
        stop.text_color = (0, 0, 0, 1)

        play = CircleButton(text="PLAY")
        play.bind(on_release=lambda _: print("do play"))
        play.font_size = '12sp'
        play.stroke_color = (0, 0, 0, 0)
        play.text_color = (0, 0, 0, 1)

        radio = CircleButton(text="RADIO")
        radio.bind(on_release=self.on_radio)
        radio.font_size = '12sp'
        radio.stroke_color = (0, 0, 0, 0)
        radio.text_color = (0, 0, 0, 1)

        save = CircleButton(text="❤️")
        save.bind(on_release=lambda _: AUDIO_PLAYER.save_current())
        save.font_size = '16sp'
        save.custom_font = "ArialUnicode"
        save.stroke_color = (0, 0, 0, 0)
        save.text_color = (1, 0, 0, 1)

        buttons.add_widget(play)
        buttons.add_widget(stop)
        buttons.add_widget(radio)
        buttons.add_widget(save)

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
    last_data = None
    bar_count = 12

    def __init__(self, **kwargs):
        self.canvas = RenderContext(
            use_parent_projection=True,
            use_parent_modelview=True,
            use_parent_frag_modelview=False
        )
        super(VinylWidget, self).__init__(**kwargs)
        Clock.schedule_interval(self.update_glsl, 1 / 60.)
        self.audio_texture = Texture.create(size=(self.bar_count, 2), colorfmt='luminance')
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

        if AUDIO_PLAYER.data and AUDIO_PLAYER.current_state == AudioState.PLAYING:
            # Update the audio texture with new data
            audio_data = AUDIO_PLAYER.data
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            # audio_array = self.data_to_fft(audio_data)
            # audio_array = audio_array / 2
            audio_bytes = audio_array.tobytes()
            self.audio_texture.blit_buffer(audio_bytes, colorfmt='luminance', bufferfmt='float')
        else:
            audio_data = np.zeros(AUDIO_PLAYER.buffersize, dtype=np.float32).tobytes()
            self.audio_texture.blit_buffer(audio_data, colorfmt='luminance', bufferfmt='float')
        
        self.set_channel()
        

    def normalize_data(self, data):
        min_val = np.min(data)
        max_val = np.max(data)
        if max_val == min_val:
            return data
        return (data - min_val) / (max_val - min_val)

    
    def data_to_fft(self, data):
        # Convert raw data to numpy array
        data = np.frombuffer(data, dtype=np.int16) / 2

        # scale data to be between 0 and 1.  Do this here instead of calling normalize data
        # because we want to keep the data as an int16 for the fft
        data = (data - np.min(data)) / (np.max(data) - np.min(data))


        fft = np.fft.rfft(data, n=AUDIO_PLAYER.buffersize)
        indices = np.linspace(0, len(fft), self.bar_count + 1).astype(int)

        bars = np.array([np.mean(np.abs(fft[indices[i]:indices[i+1]])) for i in range(self.bar_count)])


        return bars



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
