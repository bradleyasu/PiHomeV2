from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse
from kivy.clock import Clock
from random import randint

from screens.NewYearsEve.firework import Firework

class Fireworks(Widget):
    is_big_firework = False
    counter = 0
    def __init__(self, **kwargs):
        super(Fireworks, self).__init__(**kwargs)
        self.fireworks = []

    def explode_firework(self, dt):
        # Create a new firework at a random position
        # create random float between 0 and 1
        rand_red = randint(0, 100) / 100
        rand_green = randint(0, 100) / 100
        rand_blue = randint(0, 100) / 100
        rand_opacity = randint(80, 100) / 100
        color = [rand_red, rand_green, rand_blue, rand_opacity]  # White color with alpha
        if self.is_big_firework == True:
            self.counter += 1
        if self.counter > 100:
            self.is_big_firework = False
            self.counter = 0
        with self.canvas:
            Color(*color)
            firework = Firework(pos=(randint(-200, self.width - 10), randint(-200, self.height - 10)), size=(10, 10))
            if self.is_big_firework == True:
                firework.max_fireworks_size = randint(500, 1200)
                firework.pos_step = 0
        self.fireworks.append(firework)

    def update_fireworks(self, dt):
        # Update the size of each firework and remove if too big
        for firework in self.fireworks[:]:
            firework.step()
            if firework.size[0] > firework.max_fireworks_size:
                self.canvas.remove(firework)
                self.fireworks.remove(firework)

    def start_fireworks(self):
        # Schedule the continuous creation of fireworks and their updates
        Clock.schedule_interval(self.explode_firework, 0.2)
        Clock.schedule_interval(self.update_fireworks, 0.03)

    def stop_fireworks(self):
        # Stop the fireworks
        Clock.unschedule(self.explode_firework)
        Clock.unschedule(self.update_fireworks)
        self.canvas.clear()
        self.fireworks = []