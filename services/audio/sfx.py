import os
import subprocess
import signal
from util.phlog import PIHOME_LOGGER
from util.configuration import CONFIG

class PihomeSfx:
    path = "assets/audio/sfx/"
    SOURCES = {}
    SOUND_PROCESSES = {}  # Track running ffplay processes

    def __init__(self, **kwargs):
        super(PihomeSfx, self).__init__(**kwargs)
        self.populate_sources()
        # Get ALSA device from config
        self.device = CONFIG.get('audio', 'device', 'default')
        if self.device == "auto" or self.device == "":
            self.device = "default"
        PIHOME_LOGGER.info(f"SFX will use ALSA device: {self.device}")

    def load_sfx(self, key):
        """Check if sound effect exists (no pre-loading needed with subprocess)"""
        if key not in self.SOURCES:
            PIHOME_LOGGER.warn(f"Sound effect '{key}' not found in sources")
            return False
        return True

    def play(self, key):
        """Play a sound effect using ffplay subprocess"""
        PIHOME_LOGGER.info(f"Playing sound effect: {key}")
        
        if key not in self.SOURCES:
            PIHOME_LOGGER.error(f"Sound effect '{key}' not found")
            return None
        
        # Stop any existing playback of this sound
        self.stop(key)
        
        sound_file = self.SOURCES[key]
        
        try:
            # Use ffplay with ALSA output (respects .asoundrc via default device)
            # -nodisp: no video display
            # -autoexit: exit when done
            # -loglevel quiet: suppress output
            cmd = [
                'ffplay',
                '-nodisp',
                '-autoexit',
                '-loglevel', 'quiet',
                sound_file
            ]
            
            # Start process in background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            
            # Store process reference
            self.SOUND_PROCESSES[key] = process
            
            PIHOME_LOGGER.debug(f"Started ffplay process {process.pid} for {key}")
            return process
            
        except Exception as e:
            PIHOME_LOGGER.error(f"Error playing sound effect '{key}': {e}")
            return None

    def loop(self, key):
        """Loop a sound effect using ffplay subprocess"""
        PIHOME_LOGGER.info(f"Looping sound effect: {key}")
        
        if key not in self.SOURCES:
            PIHOME_LOGGER.error(f"Sound effect '{key}' not found")
            return None
        
        # Stop any existing playback of this sound
        self.stop(key)
        
        sound_file = self.SOURCES[key]
        
        try:
            # Use ffplay with loop option
            cmd = [
                'ffplay',
                '-nodisp',
                '-loop', '0',  # Loop indefinitely
                '-loglevel', 'quiet',
                sound_file
            ]
            
            # Start process in background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            
            # Store process reference
            self.SOUND_PROCESSES[key] = process
            
            PIHOME_LOGGER.debug(f"Started looping ffplay process {process.pid} for {key}")
            return process
            
        except Exception as e:
            PIHOME_LOGGER.error(f"Error looping sound effect '{key}': {e}")
            return None

    def stop(self, key):
        """Stop a playing sound effect"""
        if key in self.SOUND_PROCESSES:
            process = self.SOUND_PROCESSES[key]
            if process and process.poll() is None:  # Process still running
                PIHOME_LOGGER.info(f"Stopping sound effect: {key}")
                try:
                    process.terminate()
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                except Exception as e:
                    PIHOME_LOGGER.error(f"Error stopping sound effect '{key}': {e}")
            
            # Remove from dict
            del self.SOUND_PROCESSES[key]

    def has(self, key):
        """Check if a sound effect exists"""
        return key in self.SOURCES

    def cleanup(self):
        """Stop all playing sound effects and cleanup"""
        PIHOME_LOGGER.info("Cleaning up SFX processes...")
        for key in list(self.SOUND_PROCESSES.keys()):
            self.stop(key)

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