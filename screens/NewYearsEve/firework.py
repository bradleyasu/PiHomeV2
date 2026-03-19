import math
from random import uniform, randint


class FireworkParticle:
    """Lightweight data object for a single firework particle."""
    __slots__ = ('x', 'y', 'vx', 'vy', 'r', 'g', 'b', 'opacity', 'size', 'life', 'age')

    def __init__(self, x, y, vx, vy, r, g, b, size=4.0, life=1.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.r = r
        self.g = g
        self.b = b
        self.opacity = 1.0
        self.size = size
        self.life = life
        self.age = 0.0

    def tick(self, dt, gravity):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy -= gravity * dt
        progress = min(self.age / self.life, 1.0)
        self.opacity = max(0.0, 1.0 - progress)
        self.size = max(0.5, self.size * (1.0 - 0.3 * dt))

    def is_dead(self):
        return self.age >= self.life


class FireworkBurst:
    """A group of particles that burst outward from a single origin point."""

    GRAVITY = 40.0

    def __init__(self, cx, cy, color_palette, particle_count=20):
        self.particles = []
        angle_step = (2 * math.pi) / particle_count
        for i in range(particle_count):
            angle = angle_step * i + uniform(-0.15, 0.15)
            speed = uniform(80, 160)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            r, g, b = color_palette[i % len(color_palette)]
            size = uniform(3.0, 6.0)
            life = uniform(0.6, 1.2)
            self.particles.append(FireworkParticle(cx, cy, vx, vy, r, g, b, size, life))

    def tick(self, dt):
        for p in self.particles:
            if not p.is_dead():
                p.tick(dt, self.GRAVITY)

    def is_dead(self):
        return all(p.is_dead() for p in self.particles)

    def get_draw_data(self):
        result = []
        for p in self.particles:
            if not p.is_dead() and p.opacity > 0.02:
                result.append((p.x, p.y, p.size, p.r, p.g, p.b, p.opacity))
        return result
