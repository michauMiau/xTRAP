import pygame

class GMeter:
    def __init__(self, x, y, radius):
        self.x = x
        self.y = y
        self.radius = radius

    def draw(self, surface, ax, ay):
        pygame.draw.circle(surface, (100,100,100), (self.x,self.y), self.radius, 2)

        dx = max(-1, min(1, ax / 9.81))
        dy = max(-1, min(1, ay / 9.81))

        scale = 0.2  # tweak this
        dx = int((ax / 9.81) * self.radius * scale)
        dy = int((ay / 9.81) * self.radius * scale)
#         dy = int(dy * self.radius * 0.8)
        # The G Meter text is in MAIN.PY
        pygame.draw.circle(surface, (255,0,0), (self.x+dx, self.y+dy), 5)