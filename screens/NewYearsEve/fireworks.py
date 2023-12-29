from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse
from kivy.clock import Clock
from random import randint

from screens.NewYearsEve.firework import Firework

class Fireworks(Widget):
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
        max_size = randint(50, 200)
        with self.canvas:
            Color(*color)
            firework = Firework(pos=(randint(0, self.width - 10), randint(0, self.height - 10)), size=(10, 10))
            firework.max_fireworks_size = max_size 
        self.fireworks.append(firework)

    def update_fireworks(self, dt):
        # Update the size of each firework and remove if too big
        for firework in self.fireworks[:]:
            firework.size = (firework.size[0] + 2, firework.size[1] + 2)
            firework.pos = (firework.pos[0] + 0.5, firework.pos[1] + 0.5)
            if firework.size[0] > firework.max_fireworks_size:
                self.canvas.remove(firework)
                self.fireworks.remove(firework)

    def start_fireworks(self):
        # Schedule the continuous creation of fireworks and their updates
        Clock.schedule_interval(self.explode_firework, 0.1)
        Clock.schedule_interval(self.update_fireworks, 0.03)

    def stop_fireworks(self):
        # Stop the fireworks
        Clock.unschedule(self.explode_firework)
        Clock.unschedule(self.update_fireworks)
        self.canvas.clear()
        self.fireworks = []