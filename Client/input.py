import pygame
from state import state
from network import send_steering

# default
state.steer = 180

STEER_STEP = 2

def handle_input():
    keys = pygame.key.get_pressed()

    new_angle = state.steer

    if keys[pygame.K_LEFT]:
        new_angle -= STEER_STEP

    if keys[pygame.K_RIGHT]:
        new_angle += STEER_STEP

    # clamp
    new_angle = max(0, min(180, new_angle))

    # only send if changed
    if new_angle != state.steer:
        state.steer = new_angle
        send_steering(new_angle)