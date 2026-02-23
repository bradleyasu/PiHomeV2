
from kivy.clock import Clock
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivy.graphics import RenderContext
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.image import Image

from interface.pihomescreen import PiHomeScreen
from kivy.lang import Builder



# Plasma shader
pulse_shader = '''
$HEADER$

uniform vec2 resolution;
uniform float time;

vec3 hsb2rgb(in vec3 c)
{
    vec3 rgb = clamp(abs(mod(c.x*6.0+vec3(0.0,4.0,2.0),
                             6.0)-3.0)-1.0,
                     0.0,
                     1.0 );
    rgb = rgb*rgb*(3.0-2.0*rgb);
    return c.z * mix( vec3(1.0), rgb, c.y);
}

void main(void)
{

    // if time is greater than 4 seconds, discard the pixel
    if (time > 2.0) {
        discard;
    }

    vec2 p=(2.0*gl_FragCoord.xy-resolution.xy)/resolution.y;

    // move to bottom of screen
    p.y += 1.5;

    float r = length(p) * 0.15;

    vec3 color = hsb2rgb(vec3(0, 0.2, 1.0));
    float opacity = 1.0;

    float a = pow(r, 2.0);
    float b = sin(r * 0.1 - 1.6);
    float c = asin(r - 0.010);
    float s = sin(a - time * 3.0 + b) * c;

    color *= abs(1.0 / (s * 10.8)) - 0.1;
    opacity = 1.0 / (s * 10.8) - 0.1;

    // Convert Black to Transparent
    if (color.r < 0.1 && color.g < 0.1 && color.b < 0.1) {
        color = vec3(0.0, 0.0, 0.0);
        opacity = 0.0;
    }

    // if the radius is greater than 1, discard the pixel
    if (r > 0.5) {
        discard;
    }


    gl_FragColor = vec4(color, opacity);
}
'''


Builder.load_file("./components/PulseWidget/PulseWidget.kv")
class PluseWidget(FloatLayout):

    # property to set the source code for fragment shader
    fs = StringProperty()
    time = NumericProperty(4.0)

    def __init__(self, **kwargs):
        # Instead of using Canvas, we will use a RenderContext,
        # and change the default shader used.
        self.canvas = RenderContext()

        # call the constructor of parent
        # if they are any graphics object, they will be added on our new canvas
        super(PluseWidget, self).__init__(**kwargs)
        self.run()


    def burst(self):
        self.time = 0.0;
        print("Burst")


    def run(self, *args):
        # We'll update our glsl variables in a clock
        Clock.schedule_interval(self.update_glsl, 1 / 60.)


    def on_fs(self, instance, value):
        # set the fragment shader to our source code
        shader = self.canvas.shader
        old_value = shader.fs
        shader.fs = value
        if not shader.success:
            shader.fs = old_value
            raise Exception('failed')

    def update_glsl(self, *largs):
        self.time = self.time + (1/15.)
        self.canvas['time'] = self.time #Clock.get_boottime()
        self.canvas['resolution'] = list(map(float, self.size))
        
        self.canvas['audioTexture'] = 1


        # This is needed for the default vertex shader.
        win_rc = Window.render_context
        self.canvas['projection_mat'] = win_rc['projection_mat']
        self.canvas['modelview_mat'] = win_rc['modelview_mat']
        self.canvas['frag_modelview_mat'] = win_rc['frag_modelview_mat']


PULSER = PluseWidget(fs=pulse_shader)