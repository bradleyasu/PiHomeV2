from kivy.lang import Builder

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import RenderContext, Fbo, ClearBuffers, ClearColor
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty

from interface.pihomescreen import PiHomeScreen
from screens.HomeAssistantScreen.HomeAssistantMediaPlayer import HomeAssistantMediaPlayer
from services.homeassistant.homeassistant import HOME_ASSISTANT, HomeAssistantListener

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

Builder.load_file("./screens/HomeAssistantScreen/HomeAssistantScreen.kv")
class HomeAssistantScreen(PiHomeScreen):

    media_player_widget = HomeAssistantMediaPlayer("media_player.unknown")

    def __init__(self, **kwargs):
        super(HomeAssistantScreen, self).__init__(**kwargs)
        self.listener = HomeAssistantListener(self.on_state_change)
        HOME_ASSISTANT.add_listener(self.listener)

        # screen_root = self.ids["home_assistant_screen_root"]

        # add a HomeAssistantMediaPlayer 
        shader_widget = ShaderWidget(size_hint=(1, 1))
        layout = FloatLayout()
        layout.add_widget(shader_widget)
        layout.add_widget(self.media_player_widget)
        self.add_widget(layout)
        # screen_root.add_widget(shader_widget)
        # screen_root.add_widget(self.media_player_widget)

    def on_pre_enter(self, *args):
        for state in HOME_ASSISTANT.current_states:
            # if state is a media player, add a HomeAssistantMediaPlayer
            if "media_player" in state:
                # self.ids["home_assistant_screen_root"].add_widget(widget)
                pass
        return super().on_pre_enter(*args)


    def on_rotary_down(self):
        self.media_player_widget.media_player_play_pause()

    def on_rotary_turn(self, direction, button_pressed):
        if direction == -1:
            self.media_player_widget.decrease_volume()
        elif direction == 1:
            self.media_player_widget.increase_volume()


    def on_state_change(self, id, state, data):
        if "media_player" in id and "spotify_" not in id:
            self.media_player_widget.entity_id = id
            self.media_player_widget.on_state_change(id, state, data)


class ShaderWidget(Widget):
    def __init__(self, **kwargs):
        self.canvas = RenderContext()  # Create a RenderContext for the shader
        super(ShaderWidget, self).__init__(**kwargs)
        self.canvas.shader.fs = plasma_shader  # Set the fragment shader code
        self.time = 0  # Initialize time uniform
        
        self.pos_hint = {"center_x": 0, "center_y": 0}
        with self.canvas:
            self.fbo = Fbo(size=self.size)
            self.fbo.shader.fs = plasma_shader
        
        # Schedule updates
        Clock.schedule_interval(self.update_shader, 1 / 60.)
        
    def update_shader(self, dt):
        # Update time and pass the resolution and time to the shader
        self.time += dt
        self.canvas['time'] = self.time
        self.canvas['resolution'] = list(map(float, self.size))  # Send resolution as uniform

    def on_size(self, *args):
        # Ensure the FBO size matches the widget size
        self.fbo.size = self.size