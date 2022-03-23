import kivy
from kivy.app import App
from kivy.uix.button import Button

from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout

from components.Reveal.reveal import Reveal
from screens.Home.home import HomeScreen
from screens.Settings.settings import SettingsScreen
from util.configuration import Configuration
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen

# Run PiHome on Kivy 2.0.0
kivy.require('2.0.0')

# Hide Cursor
# Window.show_cursor = False


class PiHome(App):

    def __init__(self, **kwargs):
        super(PiHome, self).__init__(**kwargs)
        self.base_config = Configuration('base.ini')
        self.height = self.base_config.get_int('window', 'height', 480)
        self.width = self.base_config.get_int('window', 'width', 800)
        # Create the Screenmanager

    def setup(self):
        Window.size = (self.width, self.height)
        self.screens = {
            'home': HomeScreen(name = 'home'),
            'settings': SettingsScreen(name = 'settings')
        }

    # the root widget
    def build(self):
        self.setup()
        screenManager = ScreenManager()
        # button = Button(text=self.base_config.get('test', 'phrase', 'quit'))
        # button.bind(on_press=lambda _: PiHome.get_running_app().stop())
        # reveal = Reveal()
        # reveal2 = Reveal()
        # reveal3 = Reveal()
        # reveal.add_top_widget(Label(text="PiHome"))
        # reveal.add_bottom_widget(button)

        # reveal2.add_top_widget(Label(text="Another one"))
        # reveal2.add_bottom_widget(Label(text="bottom"))

        # layout = GridLayout(rows=4)

        # layout.add_widget(Button(text="test"))
        # layout.add_widget(reveal)
        # layout.add_widget(reveal2)
        # layout.add_widget(Reveal())
        # Add few screens
        for screen in self.screens.values():
            # screen = Screen(name='Title %d' % i)
            # screen.add_widget(HomeScreen(name = 'home'))
            screenManager.add_widget(screen)

        return screenManager


# Start PiHome
PiHome().run()
