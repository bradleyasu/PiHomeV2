import os
from kivy.core.audio import SoundLoader

from util.phlog import PIHOME_LOGGER

class PihomeSfx:
    path = "assets/audio/sfx/"
    SOURCES = {}

    SOUND_EFFECTS = {}

    def __init__(self, **kwargs):
        super(PihomeSfx, self).__init__(**kwargs)
        self.populate_sources()
        self.load_sfx()

    def load_sfx(self):
        for key, value in self.SOURCES.items():
            try:
                self.SOUND_EFFECTS[key] = SoundLoader.load(value)
            except Exception as e:
                PIHOME_LOGGER.error("Error loading sound effect: {}".format(e))

    def play(self, key):
        PIHOME_LOGGER.info("Playing sound effect: {}".format(key))
        if key in self.SOUND_EFFECTS and self.SOUND_EFFECTS[key] is not None:
            self.SOUND_EFFECTS[key].load()
            self.SOUND_EFFECTS[key].loop = False
            self.SOUND_EFFECTS[key].play()
            self.SOUND_EFFECTS[key].seek(0)
            self.SOUND_EFFECTS[key].bind(on_stop=lambda _: self.SOUND_EFFECTS[key].unload())
            return self.SOUND_EFFECTS[key]
        return None

    def loop(self, key):
        PIHOME_LOGGER.info("Looping sound effect: {}".format(key))
        if key in self.SOUND_EFFECTS and self.SOUND_EFFECTS[key] is not None:
            self.SOUND_EFFECTS[key].load()
            self.SOUND_EFFECTS[key].loop = True
            self.SOUND_EFFECTS[key].play()
            self.SOUND_EFFECTS[key].seek(0)
            self.SOUND_EFFECTS[key].bind(on_stop=lambda _: self.SOUND_EFFECTS[key].unload())
            return self.SOUND_EFFECTS[key]
        return None

    def stop(self, key):
        PIHOME_LOGGER.info("Stopping sound effect: {}".format(key))
        if key in self.SOUND_EFFECTS and self.SOUND_EFFECTS[key] is not None:
            self.SOUND_EFFECTS[key].stop()
            self.SOUND_EFFECTS[key].unload()

    def has(self, key):
        if key in self.SOUND_EFFECTS:
            return True
        return False

    def populate_sources(self):
        """
        SOURCES is a diction of sound effects.  This function will populate the SOURCES dictionary with the correct paths by reading 
        all the files in the sfx directory.
        """
        path = "assets/audio/sfx/"
        files = os.listdir(path)
        for file in files:
            if file.endswith(".mp3"):
                self.SOURCES[file.split(".")[0]] = "{}/{}".format(path, file)

SFX = PihomeSfx()