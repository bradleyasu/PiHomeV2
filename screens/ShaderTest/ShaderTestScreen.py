'''
Plasma Shader
=============

This shader example have been taken from
http://www.iquilezles.org/apps/shadertoy/ with some adaptation.

This might become a Kivy widget when experimentation will be done.
'''


from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import RenderContext
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.properties import StringProperty

from interface.pihomescreen import PiHomeScreen
from kivy.lang import Builder


# Plasma shader
plasma_shader = '''
$HEADER$

// Kivy-compatible shader (GLSL ES 2.0)
#ifdef GL_ES
precision mediump float;
#endif

#define S(a,b,t) smoothstep(a,b,t)

uniform float time;  // equivalent to iTime
uniform vec2 resolution;  // equivalent to iResolution

mat2 Rot(float a)
{
    float s = sin(a);
    float c = cos(a);
    return mat2(c, -s, s, c);
}

vec2 hash(vec2 p)
{
    p = vec2(dot(p, vec2(2127.1, 81.17)), dot(p, vec2(1269.5, 283.37)));
    return fract(sin(p) * 43758.5453);
}

float noise(in vec2 p)
{
    vec2 i = floor(p);
    vec2 f = fract(p);
    
    vec2 u = f * f * (3.0 - 2.0 * f);

    float n = mix(
        mix(dot(-1.0 + 2.0 * hash(i + vec2(0.0, 0.0)), f - vec2(0.0, 0.0)),
            dot(-1.0 + 2.0 * hash(i + vec2(1.0, 0.0)), f - vec2(1.0, 0.0)), u.x),
        mix(dot(-1.0 + 2.0 * hash(i + vec2(0.0, 1.0)), f - vec2(0.0, 1.0)),
            dot(-1.0 + 2.0 * hash(i + vec2(1.0, 1.0)), f - vec2(1.0, 1.0)), u.x), u.y);
    return 0.5 + 0.5 * n;
}

void main(void)
{
    vec2 uv = gl_FragCoord.xy / resolution.xy;
    float ratio = resolution.x / resolution.y;

    vec2 tuv = uv;
    tuv -= 0.5;

    // rotate with Noise
    float degree = noise(vec2(time * 0.1, tuv.x * tuv.y));

    tuv.y *= 1.0 / ratio;
    tuv *= Rot(radians((degree - 0.5) * 720.0 + 180.0));
    tuv.y *= ratio;

    // Wave warp with sin
    float frequency = 5.0;
    float amplitude = 30.0;
    float speed = time * 2.0;
    tuv.x += sin(tuv.y * frequency + speed) / amplitude;
    tuv.y += sin(tuv.x * frequency * 1.5 + speed) / (amplitude * 0.5);

    // draw the image
    vec3 colorYellow = vec3(0.957, 0.804, 0.623);
    vec3 colorDeepBlue = vec3(0.192, 0.384, 0.933);
    vec3 layer1 = mix(colorYellow, colorDeepBlue, S(-0.3, 0.2, (tuv * Rot(radians(-5.0))).x));

    vec3 colorRed = vec3(0.910, 0.510, 0.8);
    vec3 colorBlue = vec3(0.350, 0.71, 0.953);
    vec3 layer2 = mix(colorRed, colorBlue, S(-0.3, 0.2, (tuv * Rot(radians(-5.0))).x));

    vec3 finalComp = mix(layer1, layer2, S(0.5, -0.3, tuv.y));

    vec3 col = finalComp;

    gl_FragColor = vec4(col, 1.0);
}

'''


Builder.load_file("./screens/ShaderTest/ShaderTest.kv")
class ShaderWidget(FloatLayout):

    # property to set the source code for fragment shader
    fs = StringProperty(None)

    def __init__(self, **kwargs):
        # Instead of using Canvas, we will use a RenderContext,
        # and change the default shader used.
        self.canvas = RenderContext()

        # call the constructor of parent
        # if they are any graphics object, they will be added on our new canvas
        super(ShaderWidget, self).__init__(**kwargs)

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
        self.canvas['time'] = Clock.get_boottime()
        self.canvas['resolution'] = list(map(float, self.size))
        # This is needed for the default vertex shader.
        win_rc = Window.render_context
        self.canvas['projection_mat'] = win_rc['projection_mat']
        self.canvas['modelview_mat'] = win_rc['modelview_mat']
        self.canvas['frag_modelview_mat'] = win_rc['frag_modelview_mat']


class ShaderTestScreen(PiHomeScreen):
    def __init__(self, **kwargs):
        super(ShaderTestScreen, self).__init__(**kwargs)
        self.add_widget(ShaderWidget(fs=plasma_shader))