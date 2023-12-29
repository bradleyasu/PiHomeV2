from kivy.graphics import Ellipse
from random import randint


class Firework(Ellipse):
    max_fireworks_size = randint(50, 200)
    size_step = randint(5, 20)/10
    # pos step is between 0.5 and 2
    pos_step = randint(1, 8)/10
    fifty_fifty = randint(0, 1) == 1
    if fifty_fifty:
        pos_step = -pos_step
    def __init__(self, **kwargs):
        super(Firework, self).__init__(**kwargs)

    def step(self):
        self.size = (self.size[0] + self.size_step, self.size[1] + self.size_step)
        self.pos = (self.pos[0] + self.pos_step, self.pos[1] + self.pos_step)
