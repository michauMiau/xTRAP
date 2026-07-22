"""Input handling for Kivy RC client -- keyboard, gamepad, and UI button input.

In Kivy, input comes from:
1. Kivy widget bindings (buttons in UI panels)
2. Keyboard/gamepad events -- handled here via Kivy's event system
Also DO NOT DUPLICATE FUNCTIONS OMFG!!
This module provides the high-level functions that buttons call to send commands.
"""

import logging
from kivy.core.window import Window
from state import state
import network as net

log = logging.getLogger(__name__)

# Define changable steering positions
left_steer = 45 # Utmost left steer position
center_steer = 90 # Default neutral steering position
right_steer = 135 # Utmost right steering position

def set_steer(*a, angle: float = 90):
    """Set steering to a given angle and send command via network."""
    state.steer = int(angle)
    net.send_steering(int(angle))


def set_throttle(level):
    # Handling if input is incorrect
    level = max(-100, min(100, level))  # Clamp to [-100, 100]
    state.throttle = level
    net.send_throttle(int(level))

def release_steer():
    set_steer(center_steer)


def release_throttle():
    set_throttle(0)

def on_joy_axis(win, stickid, axisid, value):
    """Handle gamepad joystick events (Linux/Steam Deck Xbox-style).
    
    Axis map:
        axis 2 = left stick X → steering (-1.0 left, 0 center, +1 right)
        axis 4 = Left Trigger  → reverse throttle (0 neutral, -1 full reverse)
        axis 5 = Right Trigger → forward throttle (+1 full forward, 0 neutral)
    
    Deadzone handling: when value crosses from active → deadzone, sends explicit
    neutral commands (steer=center, throttle=0) to prevent stale state on the car.
    """
    # Normalize raw values (gamepads sometimes send -32768..+32767)
    if abs(value) > 2.0:
        value = float(value / 32768.0)
    
    value = max(-1.0, min(1.0, value))
    
    DEADZONE = 0.1
    
    if axisid == 2:
        # Steering: linear interpolation from left_steer to right_steer
        t = (value + 1.0) / 2.0  # -1..+1 → 0..1
        angle = int(left_steer + round((right_steer - left_steer) * t))
        if abs(value) < DEADZONE:
            release_steer()
        else:
            set_steer(angle=angle)
    elif axisid == 4:
        # Left Trigger → reverse only (value is always ≤ 0 on standard pads)
        level = int(round(abs(value) * 100))
        if abs(value) < DEADZONE:
            release_throttle()
        else:
            set_throttle(-level)
    elif axisid == 5:
        # Right Trigger → forward only (value is always ≥ 0 on standard pads)
        level = int(round(max(0.0, value) * 100))
        if abs(value) < DEADZONE:
            release_throttle()
        else:
            set_throttle(level)


def setup_joystick():
    """Setup joystick event binding for gamepad input."""
    Window.bind(on_joy_axis=on_joy_axis)


def setup_button_bindings(steering_panel, throttle_panel):
    """Bind input handlers to UI buttons.
    Called from main.py's build() method after panels are created.
    Args:
        steering_panel: SteeringPanel instance with left_btn/center_btn/right_btn
        throttle_panel: ThrottlePanel instance with reverse_btn/forward_btn
    """


    if steering_panel is None or throttle_panel is None:
        return

    # Wire steering buttons (adjustable) -- release returns to center
    steering_panel.left_btn.bind(
        on_press=lambda *a: set_steer(angle=left_steer),
        on_release=lambda *a: release_steer(),
    )

    steering_panel.center_btn.bind(on_press=lambda *a: set_steer(angle=center_steer))

    steering_panel.right_btn.bind(
        on_press=lambda *a: set_steer(angle=right_steer),
        on_release=lambda *a: release_steer(),
    )

    # Wire throttle buttons -- instant full power on press, zero on release
    throttle_panel.forward_btn.bind(
        on_press=lambda *a: set_throttle(100),
        on_release=lambda *a: release_throttle(),
    )
    # Reverse: instant -100% on press, zero on release
    throttle_panel.reverse_btn.bind(
        on_press=lambda *a: set_throttle(-100),
        on_release=lambda *a: release_throttle(),
    )
