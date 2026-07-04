from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.label import Label
from theme.theme import Theme
from kivy.properties import ColorProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.uix.widget import Widget

Builder.load_file("./components/Button/simplebutton.kv")

# Shared 1xN white vertical-gradient textures. GL linearly interpolates
# between texels, so the alpha ramp is baked into the texture: with 4 texels
# (bottom -> top) of (0, 0, 0, 255), the fade is confined to roughly the top
# quarter of the button instead of spanning its whole height. Created lazily
# so importing this module never touches GL before the window exists.
_GRADIENT_CACHE = {}


def _vertical_gradient(alphas):
    """Return a cached 1xN white texture; *alphas* are listed top -> bottom
    as rendered (blit_buffer row 0 draws at the TOP of the quad — verified
    on-device; Kivy's default tex_coords are v-flipped vs raw GL order)."""
    key = tuple(alphas)
    if key not in _GRADIENT_CACHE:
        tex = Texture.create(size=(1, len(alphas)), colorfmt='rgba')
        buf = bytes(b for a in alphas for b in (255, 255, 255, a))
        tex.blit_buffer(buf, colorfmt='rgba', bufferfmt='ubyte')
        tex.mag_filter = 'linear'
        _GRADIENT_CACHE[key] = tex
    return _GRADIENT_CACHE[key]


def _gloss_texture():
    """Light falloff hugging the top edge."""
    return _vertical_gradient((255, 0, 0, 0))


def _shade_texture():
    """Mirror of the gloss: dark falloff hugging the bottom edge."""
    return _vertical_gradient((0, 0, 0, 255))


class SimpleButton(ButtonBehavior, Widget):
    background_color = ColorProperty()
    foreground_color = ColorProperty()
    pressed_color = ColorProperty()
    text = StringProperty()
    zoom = NumericProperty(1)
    # Corner rounding; previously the RoundedRectangle default (10px).
    radius = NumericProperty(dp(8))
    # Gradient textures used by the KV canvas (assigned in __init__):
    # top-edge light and bottom-edge shade.
    gloss_texture = ObjectProperty(None, allownone=True)
    shade_texture = ObjectProperty(None, allownone=True)
    # Button style. A real property (not just a constructor arg) so KV
    # expressions like `type: "primary" if ... else "secondary"` restyle the
    # button when they re-evaluate (e.g. Calendar's view toggle).
    type = StringProperty("primary")

    backgrounds={
        'primary': Theme().BUTTON_PRIMARY,
        'secondary': Theme().BUTTON_SECONDARY,
        'danger': Theme().BUTTON_DANGER
    }
    foregrounds={
        'primary': Theme().BUTTON_PRIMARY_TEXT,
        'secondary': Theme().BUTTON_SECONDARY_TEXT,
        'danger': Theme().BUTTON_PRIMARY_TEXT
    }
    accents={
        'primary': Theme().BUTTON_PRIMARY_ACCENT,
        'secondary': Theme().BUTTON_SECONDARY_ACCENT,
        'danger': Theme().BUTTON_PRIMARY_ACCENT
    }

    def __init__(self, type = None, **kwargs):
       # KV rules apply inside super().__init__, so a KV-set `type` must not be
       # clobbered by the constructor default afterwards — only assign when the
       # caller actually passed one.
       super(SimpleButton, self).__init__(**kwargs)

       if type is not None:
           self.type = type
       self._apply_type_colors()
       self.gloss_texture = _gloss_texture()
       self.shade_texture = _shade_texture()
       self.bind(state=lambda *args: self.animate())

    def on_type(self, *args):
        self._apply_type_colors()

    def _apply_type_colors(self):
        t = Theme()
        key = self.type if self.type in self.backgrounds else 'primary'
        self.background_color = t.get_color(self.backgrounds[key])
        self.foreground_color = t.get_color(self.foregrounds[key])
        self.pressed_color = t.get_color(self.accents[key])

    def animate(self):
        if self.state == 'down':
            animation = Animation(zoom=.94, t='out_quad', d=.2)
        else:
            animation = Animation(zoom=1, t='out_elastic', d=.5)
        animation.start(self)


    def bind(self, **kwargs):
        super(SimpleButton, self).bind(**kwargs)
