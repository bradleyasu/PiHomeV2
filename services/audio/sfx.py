from kivy.core.audio import SoundLoader

class PihomeSfx:
    path = "assets/audio/sfx/"
    SOURCES = {
        'pop': '{}/pop.mp3'.format(path),
        'multi_pop': '{}/multi_pop.mp3'.format(path),
        'startup': '{}/startup_2.mp3'.format(path),
        'success': '{}/success.mp3'.format(path)
    }

    SOUND_EFFECTS = {}

    def __init__(self, **kwargs):
        super(PihomeSfx, self).__init__(**kwargs)
        self.load_sfx()

    def load_sfx(self):
        for key, value in self.SOURCES.items():
            self.SOUND_EFFECTS[key] = SoundLoader.load(value)

    def play(self, key):
        if key in self.SOUND_EFFECTS and self.SOUND_EFFECTS[key] is not None:
            self.SOUND_EFFECTS[key].seek(0)
            self.SOUND_EFFECTS[key].play()

SFX = PihomeSfx()