from kivy.graphics import Ellipse
from random import randint


class Firework(Ellipse):
    max_fireworks_size = randint(50, 200)
    def __init__(self, **kwargs):
        super(Firework, self).__init__(**kwargs)

    def step(self):
        self.size = (self.size[0] + 2, self.size[1] + 2)
        self.pos = (self.pos[0] + 0.5, self.pos[1] + 0.5)
