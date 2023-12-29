from kivy.graphics import Ellipse
from random import randint


class Firework(Ellipse):
    max_fireworks_size = randint(50, 200)
    def __init__(self, **kwargs):
        super(Firework, self).__init__(**kwargs)
