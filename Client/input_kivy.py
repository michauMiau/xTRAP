"""Kivy version of input handling — replaced by Kivy button bindings in main_kivy.py

Original pygame version used key.get_pressed() for steering.
In Kivy, the steering buttons (SteeringPanel.left_btn/right_btn) handle input directly.

The original logic:
- Left arrow → decrease angle toward 0° (full left)
- Right arrow → increase angle toward 180° (full right)  
- Clamp to [0, 180] range

This is now handled in main_kivy.py by button bindings:
- left_btn.on_press → send_steering(0)   # Full left
- right_btn.on_press → send_steering(180) # Full right

Future enhancements:
- Gamepad axis support (Kivy handles gamepads natively via SDL2)
- Throttle control with 2 modes (Regular/Simulated per user spec)
"""

# --- ORIGINAL PYGAME LOGIC (kept for reference only, not used in Kivy version) ---
# import pygame
# from state import state
# from network import send_steering
# 
# # default
# state.steer = 180
# STEER_STEP = 2
# 
# def handle_input():
#     keys = pygame.key.get_pressed()
# 
#     new_angle = state.steer
# 
#     if keys[pygame.K_LEFT]:
#         new_angle -= STEER_STEP
# 
#     if keys[pygame.K_RIGHT]:
#         new_angle += STEER_STEP
# 
#     # clamp
#     new_angle = max(0, min(180, new_angle))
# 
#     # only send if changed
#     if new_angle != state.steer:
#         state.steer = new_angle
#         send_steering(new_angle)
