import os
from kivy.core.audio import SoundLoader

from util.phlog import PIHOME_LOGGER

class PihomeSfx:
    path = "assets/audio/sfx/"
    SOURCES = {}

    SOUND_EFFECTS = {}

    def __init__(self, **kwargs):
        super(PihomeSfx, self).__init__(**kwargs)
        self._on_stop_callbacks = {}
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

    def _on_play_stop(self, key, *args):
        """Callback for one-shot playback — unload the sound when it finishes."""
        if key in self.SOUND_EFFECTS and self.SOUND_EFFECTS[key] is not None:
            self.SOUND_EFFECTS[key].unload()

    def play(self, key):
        PIHOME_LOGGER.info("Playing sound effect: {}".format(key))
        # Load on-demand if not already loaded
        if key not in self.SOUND_EFFECTS or self.SOUND_EFFECTS[key] is None:
            if not self.load_sfx(key):
                PIHOME_LOGGER.error(f"Failed to load sound effect: {key}")
                return None

        if key in self.SOUND_EFFECTS and self.SOUND_EFFECTS[key] is not None:
            sfx = self.SOUND_EFFECTS[key]
            sfx.unbind(on_stop=self._on_stop_callbacks.get(key))
            callback = lambda *args, k=key: self._on_play_stop(k, *args)
            self._on_stop_callbacks[key] = callback
            sfx.load()
            sfx.loop = False
            sfx.play()
            sfx.seek(0)
            sfx.bind(on_stop=callback)
            return sfx
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
            return self.SOUND_EFFECTS[key]
        return None

    def stop(self, key):
        PIHOME_LOGGER.info("Stopping sound effect: {}".format(key))
        if key in self.SOUND_EFFECTS and self.SOUND_EFFECTS[key] is not None:
            self.SOUND_EFFECTS[key].stop()
            self.SOUND_EFFECTS[key].unload()

    def has(self, key):
        if key in self.SOUND_EFFECTS or key in self.SOURCES:
            return True
        return False

    SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".ogg")

    def populate_sources(self):
        """
        Populate the SOURCES dictionary with sound effect paths.
        Scans the global sfx directory and each screen's audio/ subdirectory.
        Screen-specific sounds are namespaced as 'screendir.filename' to avoid collisions.
        """
        # Global sound effects
        self._scan_directory("assets/audio/sfx/")
        # Screen-specific sound effects
        self._scan_screen_audio()

    def _scan_directory(self, path, prefix=None):
        """Scan a directory for compatible audio files and add them to SOURCES."""
        if not os.path.isdir(path):
            return
        for file in os.listdir(path):
            if file.endswith(self.SUPPORTED_EXTENSIONS):
                key = os.path.splitext(file)[0]
                if prefix:
                    key = f"{prefix}.{key}"
                self.SOURCES[key] = os.path.join(path, file)

    def _scan_screen_audio(self):
        """Scan all screen directories for audio/ subdirectories."""
        screens_dir = "screens/"
        if not os.path.isdir(screens_dir):
            return
        for screen in os.listdir(screens_dir):
            audio_dir = os.path.join(screens_dir, screen, "audio")
            if os.path.isdir(audio_dir):
                self._scan_directory(audio_dir, prefix=screen.lower())

SFX = PihomeSfx()