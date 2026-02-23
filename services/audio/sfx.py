
class PihomeSfx:
    path = "assets/audio/sfx/"
    SOURCES = {}

    SOUND_EFFECTS = {}

    def __init__(self, **kwargs):
        super(PihomeSfx, self).__init__(**kwargs)
        self.populate_sources()
        # Don't load SFX at init - load lazily when first played
        # This prevents locking the audio device when PiHome starts

    def load_sfx(self, key):
        pass

    def play(self, key):
        pass

    def loop(self, key):
        pass

    def stop(self, key):
        pass

    def has(self, key):
        return False

    def populate_sources(self):
        pass

SFX = PihomeSfx()