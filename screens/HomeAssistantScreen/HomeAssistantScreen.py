from kivy.lang import Builder
from kivy.properties import StringProperty
from interface.pihomescreen import PiHomeScreen
from services.homeassistant.homeassistant import HOME_ASSISTANT


Builder.load_file("./screens/HomeAssistantScreen/HomeAssistantScreen.kv")
class HomeAssistantScreen(PiHomeScreen):
    def __init__(self, **kwargs):
        super(HomeAssistantScreen, self).__init__(**kwargs)

    def on_enter(self):
        for key in HOME_ASSISTANT.current_states:
            state = HOME_ASSISTANT.current_states[key]
            print(state)