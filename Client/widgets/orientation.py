import pygame
import math

class Orientation:
    def __init__(self, x, y, radius):
        self.x = x
        self.y = y
        self.radius = radius

        # simple triangle as "vehicle"
        self.base_image = pygame.Surface((40,40), pygame.SRCALPHA)
        pygame.draw.polygon(self.base_image, (0,255,255),
            [(20,5), (35,35), (5,35)]
        )

    def draw(self, surface, ax, ay, az):
        pygame.draw.circle(surface, (100,100,100), (self.x,self.y), self.radius, 2)

        # compute roll angle
        angle = math.degrees(math.atan2(ay, az))

        rotated = pygame.transform.rotate(self.base_image, -angle)
        rect = rotated.get_rect(center=(self.x, self.y))

        surface.blit(rotated, rect)