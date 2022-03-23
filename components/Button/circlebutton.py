from kivy.app import App
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import Image  
from kivy.uix.label import Label


Builder.load_file("./components/Button/circlebutton.kv")

class CircleButton(ButtonBehavior, Label):
    def __init__(self, **kwargs):
        super(CircleButton, self).__init__(**kwargs)
        self.color = ( 0.97, 0.97, 0.97, 1)

    def on_press(self):
        self.color = ( 0.87, 0.87, 0.87, 1)
        print("press")

    def on_release(self):
        self.color = ( 0.97, 0.97, 0.97, 1)
        print("release")