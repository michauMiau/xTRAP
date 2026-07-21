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
    """Handle gamepad joystick events.
    
    Xbox/Linux standard: LT=axis 4 (0..-1 reverse), RT=axis 5 (0..+1 forward)
    Steam Deck/others may use combined bipolar axis or different IDs.
    
    Args:
        win: The window object
        stickid: Which controller (usually 0 for first pad)
        axisid: Which axis changed
        value: Position from -1.0 to 1.0 OR raw gamepad values (0..65535)
    """
    # Deadzone threshold — ignore small drift near center
    DEADZONE = 0.1
    
    # Normalize value if it's in raw range (gamepads sometimes send 0..65535 or negative raw)
    if abs(value) > 2.0:
        if value > 0:
            value = float(value / 32767.0)
        else:
            value = float(value / 32768.0)
    
    # Clamp to safe range just in case
    value = max(-1.0, min(1.0, value))
    
    # Apply deadzone — values within ±DEADZONE become 0
    if abs(value) < DEADZONE:
        return  # Don't call set_throttle at all during deadzone
    
    # Map joystick axes to controls using configurable steering variables
    if axisid == 2:
        # Axis 2 = left stick horizontal → Steering (-1.0 = full left, 1.0 = full right)
        if value < 0:
            # Left half: left_steer (45) → center_steer (90) when going -1.0 → 0.0
            angle = int(left_steer + (1.0 - abs(value)) * (center_steer - left_steer))
        else:
            # Right half: center_steer (90) → right_steer (135) when going 0.0 → 1.0
            angle = int(center_steer + value * (right_steer - center_steer))
        set_steer(angle=angle)
    elif axisid == 4:
        # Axis 4 = Left Trigger (LT) → Reverse (-1.0 = full reverse, 0.0 = neutral)
        level = int(value * 100) if value < 0 else int(abs(value) * 100)
        set_throttle(-level if value < 0 else level)
    elif axisid == 5:
        # Axis 5 = Right Trigger (RT) → Forward (+1.0 = full forward, 0.0 = neutral)
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
