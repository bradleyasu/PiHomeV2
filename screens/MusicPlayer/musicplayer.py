


from kivy.uix.widget import Widget

from interface.pihomescreen import PiHomeScreen
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.graphics import RenderContext
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import StringProperty
from kivy.core.audio import SoundLoader
from kivy.graphics.texture import Texture
import numpy as np
import alsaaudio

Builder.load_file("./screens/MusicPlayer/musicplayer.kv")
class MusicPlayerContainer(PiHomeScreen):
    sound = None
    def __init__(self, **kwargs):
        super(MusicPlayerContainer, self).__init__(**kwargs)
        self.vinyl = VinylWidget(fs=vinyl_shader)
        self.add_widget(self.vinyl)
        self.add_widget(MusicPlayerCard())

    
    def on_enter(self, *args):
        url = "https://rr3---sn-8xgp1vo-2pul.googlevideo.com/videoplayback?expire=1709337780&ei=VBjiZdeJFeG9_9EP3J2AiA8&ip=74.109.241.148&id=o-ALLuUo5hmYuUdLSWnmmfJedi9hpY8h8b58OCsN-HQCpc&itag=251&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&mh=Nn&mm=31%2C29&mn=sn-8xgp1vo-2pul%2Csn-8xgp1vo-p5qe&ms=au%2Crdu&mv=m&mvi=3&pl=18&gcr=us&initcwndbps=898750&spc=UWF9fzggasD4niyPJNKYKiVzKvYnUtZ3cbXFjsryDK4EqWs&vprv=1&svpuc=1&mime=audio%2Fwebm&gir=yes&clen=4391306&dur=278.361&lmt=1706308899802101&mt=1709315833&fvip=6&keepalive=yes&fexp=24007246&c=ANDROID&txp=4532434&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cgcr%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Cgir%2Cclen%2Cdur%2Clmt&sig=AJfQdSswRQIgQE0R0uwDzqSxnuX_9B5vtfx8_LsUlvvH__bxjLVujp0CIQCqe4oUM7hOdBOkc0gk2h60UCK-yyZZWEr08oao6fIMpw%3D%3D&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Cinitcwndbps&lsig=APTiJQcwRgIhAPaaWdV0tV5FkPYOpHN82ZKBLn27S6Dc79TMTJQigrf4AiEAq5jcfnMox5ToATXrgG4QcMyMGSUSgOOlA7yI06Rp0nY%3D&fmt=.mp3"
        self.sound = SoundLoader.load(url)
        self.sound.play()

        # get audio texture for vinyl shader
        self.vinyl.set_sound(self.sound)

        return super().on_enter(*args)

    def on_leave(self, *args):
        if self.sound:
            self.sound.stop()
            self.sound.unload()
        return super().on_leave(*args)


class MusicPlayerCard(BoxLayout):
    def __init__(self, **kwargs):
        super(MusicPlayerCard, self).__init__(**kwargs)

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
        float barAngel = texture2D(iChannel0, vec2(1. - barId / BARS, .25)).x * .5;

        // add a little rotation to completely ruin the beautiful symmetry
        tRotate(uv, -barAngel * .2 * sin(barId + time));
        
        // mirror everything
    	uv = abs(uv);
        
        // add the bars
        d = opS(d, sdArk(uv, barStart, barStart + barWidth / 2., barAngel));
    }
    
    // use the slope to render the distance with antialiasing
    float w = min(fwidth(d), .01);
	gl_FragColor = vec4(vec3(smoothstep(-w, w, d)),1.0);

}
'''

class VinylWidget(Widget):


    fs = StringProperty(None)
    sound = None

    # Define the audio parameters
    SAMPLE_RATE = 44100
    NUM_CHANNELS = 2
    SAMPLE_WIDTH = 2
    PERIOD_SIZE = 1024

    # Initialize the audio device for capture
    capture = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK)
    capture.setchannels(NUM_CHANNELS)
    capture.setrate(SAMPLE_RATE)
    capture.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    capture.setperiodsize(PERIOD_SIZE)

    def __init__(self, **kwargs):
        # Instead of using Canvas, we will use a RenderContext,
        # and change the default shader used.
        self.canvas = RenderContext()

        # call the constructor of parent
        # if they are any graphics object, they will be added on our new canvas
        super(VinylWidget, self).__init__(**kwargs)

        # We'll update our glsl variables in a clock
        Clock.schedule_interval(self.update_glsl, 1 / 60.)
        self.audio_texture = self.create_texture((1024, 1))

    def on_fs(self, instance, value):
        # set the fragment shader to our source code
        shader = self.canvas.shader
        old_value = shader.fs
        shader.fs = value
        if not shader.success:
            shader.fs = old_value
            raise Exception('failed')

    def update_glsl(self, *largs):
        self.canvas['time'] = Clock.get_boottime()
        self.canvas['resolution'] = list(map(float, self.size))
        # This is needed for the default vertex shader.
        win_rc = Window.render_context
        self.canvas['projection_mat'] = win_rc['projection_mat']
        self.canvas['modelview_mat'] = win_rc['modelview_mat']
        self.canvas['frag_modelview_mat'] = win_rc['frag_modelview_mat']

        length, data = self.capture.read()
        if length > 0:
            # Process the audio data
            audio_data = np.frombuffer(data, dtype=np.int16)

            # Update the shader program with the audio texture
            audio_texture = np.array(audio_data, dtype=np.uint8)
            self.canvas['channel0'] = 0
            self.canvas['channel0'] = audio_texture
            


    def create_texture(self, size):
        return np.zeros(size)

    def set_channel(self, texture):
        self.canvas['iChannel0'] = texture
        print("Setting channel to {}".format(texture))

    def set_center_x(self, value):
        return super().set_center_x(value)

    def set_sound(self, sound):
        self.sound = sound
