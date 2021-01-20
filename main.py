import kivy
from kivy.app import App
from kivy.uix.button import Button
from util.configuration import Configuration
from kivy.core.window import Window

# Run PiHome on Kivy 2.0.0
kivy.require('2.0.0')


class PiHome(App):

    def __init__(self, **kwargs):
        super(PiHome, self).__init__(**kwargs)
        self.base_config = Configuration('base.ini')
        self.height = self.base_config.get_int('window', 'height', 480)
        self.width = self.base_config.get_int('window', 'width', 800)

    def setup(self):
        Window.size = (self.width, self.height)

    # the root widget
    def build(self):
        self.setup()
        button = Button(text=self.base_config.get('test', 'phrase', 'hello'))
        button.bind(on_press=lambda _: print("hello"))
        return button


# Start PiHome
PiHome().run()
