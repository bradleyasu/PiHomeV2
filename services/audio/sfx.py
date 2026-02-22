import os
import subprocess
import signal
import threading
from util.phlog import PIHOME_LOGGER
from util.configuration import CONFIG

class PihomeSfx:
    path = "assets/audio/sfx/"
    SOURCES = {}
    SOUND_PROCESSES = {}  # Track running ffmpeg processes

    def __init__(self, **kwargs):
        super(PihomeSfx, self).__init__(**kwargs)
        self.populate_sources()
        # Get ALSA device from config
        self.device = CONFIG.get('audio', 'device', 'default')
        if self.device == "auto" or self.device == "":
            self.device = "default"
        PIHOME_LOGGER.info(f"SFX will use ALSA device: {self.device}")
        
        # Start a cleanup thread to reap finished processes
        self._cleanup_thread = threading.Thread(target=self._cleanup_finished_processes, daemon=True)
        self._cleanup_thread.start()
    
    def _cleanup_finished_processes(self):
        """Background thread to reap finished ffmpeg processes and prevent zombies"""
        import time
        while True:
            try:
                # Check all processes and clean up finished ones
                for key in list(self.SOUND_PROCESSES.keys()):
                    process = self.SOUND_PROCESSES.get(key)
                    if process and process.poll() is not None:  # Process has finished
                        # Reap the process to prevent zombie
                        process.wait()
                        PIHOME_LOGGER.debug(f"Cleaned up finished SFX process: {key}")
                        del self.SOUND_PROCESSES[key]
                time.sleep(1)  # Check every second
            except Exception as e:
                PIHOME_LOGGER.error(f"Error in SFX cleanup thread: {e}")
                time.sleep(1)

    def load_sfx(self, key):
        """Check if sound effect exists (no pre-loading needed with subprocess)"""
        if key not in self.SOURCES:
            PIHOME_LOGGER.warn(f"Sound effect '{key}' not found in sources")
            return False
        return True

    def play(self, key):
        """Play a sound effect using ffmpeg subprocess with explicit ALSA device"""
        PIHOME_LOGGER.info(f"Playing sound effect: {key}")
        
        if key not in self.SOURCES:
            PIHOME_LOGGER.error(f"Sound effect '{key}' not found")
            return None
        
        # Stop any existing playback of this sound
        self.stop(key)
        
        sound_file = self.SOURCES[key]
        
        try:
            # Use ffmpeg with explicit ALSA output (same approach as music player)
            # This ensures we ONLY touch hw:0,0, never hw:1,0
            cmd = [
                'ffmpeg',
                '-i', sound_file,
                '-f', 'alsa',
                '-loglevel', 'quiet',
                self.device  # Explicit ALSA device (hw:0,0 from config)
            ]
            
            # Start process in background
            # Note: Process will be reaped by _cleanup_finished_processes thread
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True  # Fully detach from parent
            )
            
            # Store process reference
            self.SOUND_PROCESSES[key] = process
            
            PIHOME_LOGGER.debug(f"Started ffmpeg process {process.pid} for {key} on {self.device}")
            return process
            
        except Exception as e:
            PIHOME_LOGGER.error(f"Error playing sound effect '{key}': {e}")
            return None

    def loop(self, key):
        """Loop a sound effect using ffmpeg subprocess with explicit ALSA device"""
        PIHOME_LOGGER.info(f"Looping sound effect: {key}")
        
        if key not in self.SOURCES:
            PIHOME_LOGGER.error(f"Sound effect '{key}' not found")
            return None
        
        # Stop any existing playback of this sound
        self.stop(key)
        
        sound_file = self.SOURCES[key]
        
        try:
            # Use ffmpeg with stream_loop for continuous playback
            # -stream_loop -1 means loop indefinitely
            cmd = [
                'ffmpeg',
                '-stream_loop', '-1',  # Loop indefinitely
                '-i', sound_file,
                '-f', 'alsa',
                '-loglevel', 'quiet',
                self.device  # Explicit ALSA device (hw:0,0 from config)
            ]
            
            # Start process in background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True  # Fully detach from parent
            )
            
            # Store process reference
            self.SOUND_PROCESSES[key] = process
            
            PIHOME_LOGGER.debug(f"Started looping ffmpeg process {process.pid} for {key} on {self.device}")
            return process
            
        except Exception as e:
            PIHOME_LOGGER.error(f"Error looping sound effect '{key}': {e}")
            return None

    def stop(self, key):
        """Stop a playing sound effect"""
        if key in self.SOUND_PROCESSES:
            process = self.SOUND_PROCESSES[key]
            if process:
                try:
                    # Check if still running
                    if process.poll() is None:
                        PIHOME_LOGGER.info(f"Stopping sound effect: {key}")
                        process.terminate()
                        try:
                            process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()  # Reap the killed process
                    else:
                        # Process already finished, just reap it
                        process.wait()
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