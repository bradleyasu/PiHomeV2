# Don't import sounddevice at module level - it initializes PortAudio and locks the DAC
# import sounddevice as sd


SAVED_URL_JSON = "radio_stations.pihome"

# enum of audio states
class AudioState:
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2
    FETCHING = 3
    BUFFERING = 4

class AudioPlayer:
    percent = 0
    title = "No Media"
    volume = 1.0
    paused = False
    album_art = None
    queue = []
    queue_pos = 0
    data = None
    volume_listeners = []
    state_listeners = []
    saves_listeners = []
    percent = 100
    is_playing = False
    current_state = AudioState.STOPPED
    current_source = None
    player_thread = None
    current_folder = None
    """
    Saved urls is an array of json objects with a "text" and "url" key
    The text is the title of the media and the url is the url to the media
    an optional "thumbnail" icon can be added as album art
    """
    saved_urls =[]


    def __init__(self, device=None, blocksize=4096, buffersize=512):
        pass
    
    def __del__(self):
        pass


    def serialize_saved_urls(self):
        pass

    def deserialize_saved_urls(self):
        pass

    def save_current(self):
        pass

    def remove_saved_url(self, url):
        pass
    
    def add_save_current_from_json(self, json):
        pass

    def find_saved_url(self, url):
        pass
    
    def save_exists(self, url):
        pass

    def add_saved_url_from_json(self, json):
        pass

    def add_saved_url(self, text, url, thumbnail=None):
        pass


    def find_sound_device(self):
        pass
    
    def log_sound_devices(self):
        pass
    
    def int_or_str(self, text):
        pass

    def add_volume_listener(self, listener):
        pass

    def add_state_listener(self, listener):
        pass

    def notify_state_listeners(self, state):
        pass

    def add_saves_listener(self, listener):
        pass
    
    def notify_saves_listeners(self, saves):
        pass

    def set_state(self, state):
        pass

    def audio_processing_thread(self):
        pass

    def callback(self, outdata, frames, time, status):
        pass

    def play(self, url, reset_playlist=True):
        pass

    def _play(self, url):
        pass

    def extract_metadata(self, url):
        pass
       

    def stop(self, clear_playlist=False):
        pass
    
    def cleanup(self):
        """Full cleanup including device release"""
        return None

    def set_volume(self, volume, oneAsHundred=False):
        pass

    def volume_up(self):
        pass

    def volume_down(self):
        pass

    def next(self):
        pass

    def prev(self):
        pass

    def clear_playlist(self):
        pass

    def add_to_playlist(self, url):
        pass

    def pop_playlist(self, index=0):
        pass

    def run_youtubedl(self, url):
        pass


# Read audio device from configuration
# Support formats: hw:0,0 (ALSA), "Device Name", or None for auto-detect
_audio_device = None
AUDIO_PLAYER = AudioPlayer(device=_audio_device)
