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
        # Don't load SFX at init - load lazily when first played
        # This prevents locking the audio device when PiHome starts

    def load_sfx(self, key):
        """Load a specific sound effect on-demand"""
        if key not in self.SOURCES:
            PIHOME_LOGGER.warn(f"Sound effect '{key}' not found in sources")
            return False
        
        if key in self.SOUND_EFFECTS and self.SOUND_EFFECTS[key] is not None:
            return True  # Already loaded
        
        try:
            PIHOME_LOGGER.info(f"Loading sound effect: {key}")
            self.SOUND_EFFECTS[key] = SoundLoader.load(self.SOURCES[key])
            return self.SOUND_EFFECTS[key] is not None
        except Exception as e:
            PIHOME_LOGGER.error(f"Error loading sound effect '{key}': {e}")
            return False

    def play(self, key):
        PIHOME_LOGGER.info("Playing sound effect: {}".format(key))
        # Load on-demand if not already loaded
        if key not in self.SOUND_EFFECTS or self.SOUND_EFFECTS[key] is None:
            if not self.load_sfx(key):
                PIHOME_LOGGER.error(f"Failed to load sound effect: {key}")
                return None
        
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
        # Load on-demand if not already loaded
        if key not in self.SOUND_EFFECTS or self.SOUND_EFFECTS[key] is None:
            if not self.load_sfx(key):
                PIHOME_LOGGER.error(f"Failed to load sound effect: {key}")
                return None
        
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