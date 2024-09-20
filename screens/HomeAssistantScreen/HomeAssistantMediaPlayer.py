import time
from kivy.lang import Builder
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ColorProperty
from services.homeassistant.homeassistant import HOME_ASSISTANT, HomeAssistantListener



Builder.load_file("./screens/HomeAssistantScreen/HomeAssistantMediaPlayer.kv")

class HomeAssistantMediaPlayer(BoxLayout):

    label_color = ColorProperty([1, 1, 1, 1])

    media_player_title = StringProperty("No Title")
    media_player_artist = StringProperty("Unknown Artist")
    media_player_album = StringProperty("Unknown Album")
    media_player_name = StringProperty("")
    media_player_app = StringProperty("")
    media_player_thumbnail = StringProperty("")
    media_player_volume = NumericProperty(0)
    media_player_is_muted = BooleanProperty(False)
    media_player_duration = NumericProperty(0)
    media_player_position = NumericProperty(0)

    # epoch timestamp for when the media player was last updated
    last_updated = 0

    # debounce time
    debounce_time = 0.5

    def __init__(self, entity_id, **kwargs):
        super(HomeAssistantMediaPlayer, self).__init__(**kwargs)
        self.entity_id = entity_id
        self.listener = HomeAssistantListener(self.on_state_change)
        HOME_ASSISTANT.add_listener(self.listener)

    
    def increase_volume(self):
        HOME_ASSISTANT.update_service("media_player", "volume_up", self.entity_id, {})
        self.last_updated = time.time()
    
    def decrease_volume(self):
        HOME_ASSISTANT.update_service("media_player", "volume_down", self.entity_id, {})
        self.last_updated = time.time()

    def media_player_play_pause(self):
        HOME_ASSISTANT.update_service("media_player", "media_play_pause", self.entity_id, {})
        self.last_updated = time.time()

    def media_player_next(self):
        HOME_ASSISTANT.update_service("media_player", "media_next_track", self.entity_id, {})
        self.last_updated = time.time()

    def media_player_previous(self):
        HOME_ASSISTANT.update_service("media_player", "media_previous_track", self.entity_id, {})
        self.last_updated = time.time()

    def set_volume(self, volume):
        HOME_ASSISTANT.update_service("media_player", "volume_set", self.entity_id, {"volume_level": volume})
        self.last_updated = time.time()

    def on_state_change(self, id, state, data):

        #verify debounce time
        current_time = time.time()
        if current_time - self.last_updated < self.debounce_time:
            return

        if self.entity_id == id:
            print(f"State changed: {id} to {state}")
            try:
                self.media_player_title = data["attributes"]["media_title"]
                self.media_player_album = data["attributes"]["media_album_name"]
                self.media_player_artist = data["attributes"]["media_artist"]
                self.media_player_name = data["attributes"]["friendly_name"]
                self.media_player_app = data["attributes"]["app_name"]
                self.media_player_thumbnail = data["attributes"]["entity_picture"]
                self.media_player_volume = data["attributes"]["volume_level"]
                self.media_player_is_muted = data["attributes"]["is_volume_muted"]
                self.media_player_duration = data["attributes"]["media_duration"]
                self.media_player_position = data["attributes"]["media_position"]
                
                # check if media_player_thumbnail starts with http
                if not self.media_player_thumbnail.startswith("http"):
                    self.media_player_thumbnail = ""

            except KeyError:
                pass

