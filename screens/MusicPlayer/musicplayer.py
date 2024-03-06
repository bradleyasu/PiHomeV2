


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

Builder.load_file("./screens/MusicPlayer/musicplayer.kv")
class MusicPlayerContainer(PiHomeScreen):
    sound = None
    def __init__(self, **kwargs):
        super(MusicPlayerContainer, self).__init__(**kwargs)
        self.vinyl = VinylWidget(fs=vinyl_shader)
        self.add_widget(self.vinyl)
        self.add_widget(MusicPlayerCard())

    
    def on_enter(self, *args):
        # url = "https://rr3---sn-8xgp1vo-2pul.googlevideo.com/videoplayback?expire=1709337780&ei=VBjiZdeJFeG9_9EP3J2AiA8&ip=74.109.241.148&id=o-ALLuUo5hmYuUdLSWnmmfJedi9hpY8h8b58OCsN-HQCpc&itag=251&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&mh=Nn&mm=31%2C29&mn=sn-8xgp1vo-2pul%2Csn-8xgp1vo-p5qe&ms=au%2Crdu&mv=m&mvi=3&pl=18&gcr=us&initcwndbps=898750&spc=UWF9fzggasD4niyPJNKYKiVzKvYnUtZ3cbXFjsryDK4EqWs&vprv=1&svpuc=1&mime=audio%2Fwebm&gir=yes&clen=4391306&dur=278.361&lmt=1706308899802101&mt=1709315833&fvip=6&keepalive=yes&fexp=24007246&c=ANDROID&txp=4532434&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cgcr%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Cgir%2Cclen%2Cdur%2Clmt&sig=AJfQdSswRQIgQE0R0uwDzqSxnuX_9B5vtfx8_LsUlvvH__bxjLVujp0CIQCqe4oUM7hOdBOkc0gk2h60UCK-yyZZWEr08oao6fIMpw%3D%3D&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Cinitcwndbps&lsig=APTiJQcwRgIhAPaaWdV0tV5FkPYOpHN82ZKBLn27S6Dc79TMTJQigrf4AiEAq5jcfnMox5ToATXrgG4QcMyMGSUSgOOlA7yI06Rp0nY%3D&fmt=.mp3"
        # self.sound = SoundLoader.load(url)
        # self.sound.play()

        # get audio texture for vinyl shader
        # self.vinyl.set_sound(self.sound)
        AUDIO_PLAYER.play("https://manifest.googlevideo.com/api/manifest/hls_playlist/expire/1709760545/ei/wYvoZa2gArjB_9EPy9-FiAM/ip/74.109.241.148/id/AS_x4uR87Kw.1/itag/234/source/yt_live_broadcast/requiressl/yes/ratebypass/yes/live/1/goi/133/sgoap/gir%3Dyes%3Bitag%3D140/rqh/1/hls_chunk_host/rr1---sn-8xgp1vo-2pue.googlevideo.com/xpc/EgVo2aDSNQ%3D%3D/playlist_duration/3600/manifest_duration/3600/vprv/1/playlist_type/DVR/initcwndbps/838750/mh/Op/mm/44/mn/sn-8xgp1vo-2pue/ms/lva/mv/m/mvi/1/pl/18/dover/13/pacing/0/short_key/1/keepalive/yes/fexp/24007246/mt/1709738443/sparams/expire,ei,ip,id,itag,source,requiressl,ratebypass,live,goi,sgoap,rqh,xpc,playlist_duration,manifest_duration,vprv,playlist_type/sig/AJfQdSswRgIhAOzZAUN4D1sVs8EGPBbf1CdrAHlvX6TKkx_XAizOGoPTAiEAm47jpaARjoi11MqBdNGVlPHZZ5A6DBOCel3QxVoZGdw%3D/lsparams/hls_chunk_host,initcwndbps,mh,mm,mn,ms,mv,mvi,pl/lsig/APTiJQcwRQIhAMZQ4avWg-eNN6Tgiv4SUS_giCZwKg5GLb2rO9rbty7GAiAQ5lpxiI5zXVx0nIoPLj4mtf1OGjWgdoroG2A7BJZRjw%3D%3D/playlist/index.m3u8")


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


vinyl_shader = '''
$HEADER$
#define BARS 12.

#define PI 3.14159265359

uniform vec2 resolution;
uniform float time;
uniform sampler2D iChannel0;
uniform sampler2D channel0;
uniform sampler2D texture1;
uniform sampler2D texture3;
uniform sampler2D audioTexture;

// rotation transform
void tRotate(inout vec2 p, float angel) {
    float s = sin(angel), c = cos(angel);
	p *= mat2(c, -s, s, c);
}

// circle distance
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

// union
float opU(float a, float b) {
    return min(a, b);
}

// substraction
float opS(float a, float b) {
    return max(a, -b);
}

// distance function of half of an ark
// parameters: inner radius, outer radius, angle
float sdArk(vec2 p, float ir, float or, float a) {
    
    // add outer circle
    float d = sdCircle(p, or);
        
    // substract inner circle
    d = opS(d, sdCircle(p, ir));
    
    // rotate with angle
    tRotate(p, -a * PI / 2.);
    
    // clip the top
    d = opS(d, -p.y);
    
    // add circle to the top
    d = opU(d, sdCircle(p - vec2((or + ir) / 2., 0.), (or - ir) / 2.));
    return d;
}

void main(void)
{


   vec4 frag_coord = frag_modelview_mat * gl_FragCoord;

    vec2 uv = frag_coord.xy / resolution.xy ;

    // correct aspect ratio
    uv.x *= resolution.x / resolution.y;
    uv.x -= .22;
    uv.y -= .5;

    // center
    uv -= .5;

    // little white padding
    uv *= 2.05;
    // add circles
    float d = sdCircle(uv, 1.);
    d = opS(d, sdCircle(uv, .34));
    d = opU(d, sdCircle(uv, .04));

    // calculate position of the bars
    float barsStart = .37;
    float barsEnd = .94;
    float barId = floor((length(uv) -barsStart) / (barsEnd - barsStart) * BARS);

    // only go forward if we're in a bar
    if (barId >= 0. && barId < BARS) {
        
        float barWidth = (barsEnd - barsStart) / BARS;
        float barStart = barsStart + barWidth * (barId + .25);
        float barAngel = texture2D(audioTexture, vec2(1. - barId / BARS, .25)).x * .5;

        // add a little rotation to completely ruin the beautiful symmetry
        tRotate(uv, -barAngel * .2 * sin(barId + time));
        
        // mirror everything
    	uv = abs(uv);
        
        // add the bars
        d = opS(d, sdArk(uv, barStart, barStart + barWidth / 2., barAngel));
    }
    
    // use the slope to render the distance with antialiasing
    float w = min(fwidth(d), .01);

    vec4 final_color = vec4(vec3(smoothstep(-w, w, d)), 1.0);

    // replace the white in the final color with a transparent color
    //if (d > 0.0) {
    //    final_color = vec4(0., 0., 0., 0.);
    //}

	gl_FragColor = final_color;

    //float value = texture2D(iChannel0, uv).r;
    //gl_FragColor = vec4(vec3(value), 1.0);
}
'''
class VinylWidget(Widget):
    fs = StringProperty(None)
    sound = None
    audio_texture = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.canvas = RenderContext()
        super(VinylWidget, self).__init__(**kwargs)
        Clock.schedule_interval(self.update_glsl, 1 / 60.)
        # self.audio_texture = self.create_texture((512, 1))
        self.audio_texture = Texture.create(size=(1, 512), colorfmt='luminance')

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
        win_rc = Window.render_context
        self.canvas['projection_mat'] = win_rc['projection_mat']
        self.canvas['modelview_mat'] = win_rc['modelview_mat']
        self.canvas['frag_modelview_mat'] = win_rc['frag_modelview_mat']

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
        glActiveTexture(GL_TEXTURE3)
        glBindTexture(GL_TEXTURE_2D, self.audio_texture.id)
        self.canvas['audioTexture'] = 3 # Set to texture unit 0
        self.canvas.ask_update()
        glBindTexture(GL_TEXTURE_2D, 0)

    def set_center_x(self, value):
        return super().set_center_x(value)

    def set_sound(self, sound):
        self.sound = sound
