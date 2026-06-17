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


    # TO DO: ADD THROTTLE CONTROL AND CONTROLLER INPUT
    # Throttle shall have 2 modes, Regular: aka  when throttle  is let off it instantly goes to 0% an the robot stops
    # Simulated: The throttle behaves like an engine in this mode, when throttle is let off it gradually goes down till it stops
    # Pressing reverse will stop the robot and set throttle to 0% (functions like brakes)
    # Further press of reverse will send the car into reverse, i'm  thinking we can just send T = -100 for the throttle
    # The minus throttle will have to be handled car side.
    # This will behave like beamng on controllers then