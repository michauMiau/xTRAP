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


# --- Throttle step control for granular forward/reverse ---
_THROTTLE_STEP = 25  # Steps of 25% when holding buttons

def _forward_throttle_step():
    """Forward button: increment throttle by STEP (0 → 25 → 50 → 75 → 100)."""
    current = state.throttle
    if current < 0:
        set_throttle(0)  # Reset to neutral first
    else:
        new_level = min(current + _THROTTLE_STEP, 100)
        set_throttle(new_level)


def _reverse_throttle_step():
    """Reverse button: decrement throttle by STEP (0 → -25 → -50 → -75 → -100)."""
    current = state.throttle
    if current > 0:
        set_throttle(0)  # Reset to neutral first
    else:
        new_level = max(current - _THROTTLE_STEP, -100)
        set_throttle(new_level)


def on_joy_axis(win, stickid, axisid, value):
    """Handle gamepad joystick events.
    
    Args:
        win: The window object
        stickid: Which controller (usually 0 for first pad)
        axisid: Which axis changed (2=left x-stick, 5=right y-stick)
        value: Position from -1.0 to 1.0 OR raw gamepad values (0..65535)
    """
    # Normalize value if it's in raw range (gamepads sometimes send 0..65535 or negative raw)
    if abs(value) > 2.0:
        # Raw gamepad scale (e.g., -32768..32767 or 0..65535) → normalize to -1..1
        if value > 0:
            value = float(value / 32767.0)  # Assume signed 16-bit
        else:
            value = float(value / 32768.0)  # Assume signed 16-bit
    
    # Clamp to safe range just in case
    value = max(-1.0, min(1.0, value))
    
    # Map joystick axes to controls:
    # Axis 2 (left stick horizontal): Steering (-1.0 = full left, 1.0 = full right)
    # Axis 5 (right stick vertical): Throttle (-1.0 = reverse, 1.0 = forward)
    
    if axisid == 2:
        # Map -1..1 to 45..135 degrees for steering
        angle = int(90 + value * 45)
        set_steer(angle=angle)
    elif axisid == 5:
        # Map -1..1 to -100..100 throttle with smooth granularity
        level = int(value * 100)
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

    # Wire throttle buttons -- granular forward/reverse with step control
    # Forward: 0 → 25 → 50 → 75 → 100 (single press = +25 steps, hold for max)
    throttle_panel.forward_btn.bind(
        on_press=lambda *a: _forward_throttle_step(),
        on_release=lambda *a: release_throttle(),
    )
    # Reverse: 0 → -25 → -50 → -75 → -100 (single press = -25 steps, hold for max)
    throttle_panel.reverse_btn.bind(
        on_press=lambda *a: _reverse_throttle_step(),
        on_release=lambda *a: release_throttle(),
    )
