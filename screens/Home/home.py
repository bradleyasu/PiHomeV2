import requests
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty

from components.Button.circlebutton import CircleButton
from theme.theme import Theme
from kivy.factory import Factory

Builder.load_file("./screens/Home/home.kv")

class HomeScreen(Screen):
    theme = Theme()
    color = ColorProperty()
    image = StringProperty()
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.color = self.theme.get_color(self.theme.BACKGROUND_PRIMARY)
        # self.download_image()
        self.build()

    def build(self):
        layout = FloatLayout()
        for i in range (10):
            button = CircleButton(text=str(i), size=(dp(50), dp(50)), pos=(dp(20 + (55 * i)), dp(20)))
            layout.add_widget(button)
        
        button = CircleButton(text='#', size=(dp(50), dp(50)), pos=(dp(20), dp(self.height - 70)))
        button.bind(on_release=lambda _: self.open_settings())
        layout.add_widget(button)

        button = CircleButton(text='X', size=(dp(50), dp(50)), pos=(dp(self.width - 70), dp(self.height - 70)))
        button.bind(on_release=lambda _: App.get_running_app().stop())
        layout.add_widget(button)

        label = Label(text='PiHome')
        label.color = self.theme.get_color(self.theme.TEXT_PRIMARY)
        label.pos_hint = {'center_y': 0.5, 'center_x': 0.5}
        label.font_size = '72sp'
        layout.add_widget(label)

        self.add_widget(layout)

    def open_settings(self):
        self.manager.current = 'settings'


    def download_image(self): 

        img_data = requests.get('https://cdn.pixabay.com/photo/2018/08/14/13/23/ocean-3605547_1280.jpg').content
        with open('background.jpg', 'wb') as handler:
            handler.write(img_data)
        self.image = 'background.jpg'
