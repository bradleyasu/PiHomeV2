from kivy.lang import Builder
from kivy.properties import ListProperty
from kivy.uix.button import Button
from interface.pihomescreen import PiHomeScreen
from screens.HomeAssistantScreen.HomeAssistantMediaPlayer import HomeAssistantMediaPlayer
from services.homeassistant.homeassistant import HOME_ASSISTANT, HomeAssistantListener


Builder.load_file("./screens/HomeAssistantScreen/HomeAssistantScreen.kv")
class HomeAssistantScreen(PiHomeScreen):

    media_player_widget = HomeAssistantMediaPlayer("media_player.unknown")

    def __init__(self, **kwargs):
        super(HomeAssistantScreen, self).__init__(**kwargs)
        self.listener = HomeAssistantListener(self.on_state_change)
        HOME_ASSISTANT.add_listener(self.listener)

        screen_root = self.ids["home_assistant_screen_root"]

        # add a HomeAssistantMediaPlayer 
        screen_root.add_widget(self.media_player_widget)

    def on_pre_enter(self, *args):
        for state in HOME_ASSISTANT.current_states:
            # if state is a media player, add a HomeAssistantMediaPlayer
            if "media_player" in state:
                # self.ids["home_assistant_screen_root"].add_widget(widget)
                pass
        return super().on_pre_enter(*args)

    def on_rotary_down(self):
        self.media_player_widget.decrease_volume()

    def on_rotary_up(self):
        self.media_player_widget.increase_volume()

    def on_state_change(self, id, state, data):
        if "media_player" in id and "spotify_" not in id:
            self.media_player_widget.entity_id = id
            self.media_player_widget.on_state_change(id, state, data)