from kivy.base import runTouchApp
from kivy.lang import Builder
from kivy.uix.effectwidget import EffectWidget, EffectBase

effect_string = '''
#ifdef GL_ES
precision highp float;
#endif

uniform vec2 touch;
uniform float time;

void main(void)
{
    float dist = distance(gl_FragCoord.xy, touch);
    float strength = 0.5;  // Adjust the strength of the shockwave
    float speed = 1.5;     // Adjust the speed of the shockwave
    float ripple = smoothstep(1.0, 0.0, 1.0 - dist * speed + time * speed);
    vec3 color = vec3(1.0 - ripple * strength);
    gl_FragColor = vec4(color, 1.0);
}
'''

class ShockwaveEffect(EffectBase):
    def __init__(self, **kwargs):
        super(ShockwaveEffect, self).__init__(**kwargs)
        self.glsl = effect_string
        self.uniforms = {'touch': [0.0, 0.0], 'time': 0.0}

    def on_touch(self, touch_pos):
        self.uniforms['touch'] = touch_pos

    def on_time(self, time):
        self.uniforms['time'] = time

class Shockwave(EffectWidget):
    def __init__(self, **kwargs):
        super(Shockwave, self).__init__(**kwargs)
        self.effect = ShockwaveEffect()
        self.effects = [self.effect]

    def on_touch_down(self, touch):
        super(Shockwave, self).on_touch_down(touch)
        self.effect.on_touch(touch.pos)
        self.effect.on_time(0)  # Reset time for the new shockwave

    def on_update(self):
        self.effect.on_time(self.effect.uniforms['time'] + 0.05)

root = Builder.load_string('''
Shockwave:
    Image:
        source: 'data/logo/kivy-icon-512.png'
        fit_mode: "fill"
''')

runTouchApp(root)
