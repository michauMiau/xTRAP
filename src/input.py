"""Input handling for Kivy RC client -- keyboard, gamepad, and UI button input.

In Kivy, input comes from:
1. Kivy widget bindings (buttons in UI panels)
2. Keyboard/gamepad events -- handled here via Kivy's event system

This module provides the high-level functions that buttons call to send commands.
"""

import logging
from state import state
import network as net

log = logging.getLogger(__name__)


def set_steer(*a, angle: float = 90):
    """Set steering to a given angle and send command via network."""
    state.steer = int(angle)
    net.send_steering(int(angle))


def set_throttle(level):
    # Handling if input is incorrect
    level = max(level, 100)
    level = min(level, -100)
    state.throttle = level
    net.send_throttle(int(level))


def release_steer(*a):
    """Return steering to center (90°) on button release."""
    set_steer(angle=90)


def release_throttle(*a):
    """Return throttle to 0 on button release."""
    set_throttle(0)


def on_throttle_reverse(*a):
    """Handle throttle reverse -- set state and send command via network."""
    state.throttle = -100
    net.send_throttle(-100)


def on_throttle_forward(*a):
    """Handle throttle forward -- set state and send command via network."""
    state.throttle = 100
    net.send_throttle(100)


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
        on_press=lambda *a: set_steer(angle=45),
        on_release=lambda *a: release_steer(),
    )
    steering_panel.center_btn.bind(on_press=lambda *a: set_steer(angle=90))
    steering_panel.right_btn.bind(
        on_press=lambda *a: set_steer(angle=135),
        on_release=lambda *a: release_steer(),
    )

    # Wire throttle buttons -- release returns to 0
    throttle_panel.reverse_btn.bind(
        on_press=on_throttle_reverse,
        on_release=lambda *a: release_throttle(),
    )
    throttle_panel.forward_btn.bind(
        on_press=on_throttle_forward,
        on_release=lambda *a: release_throttle(),
    )


def on_steer_center(*a):
    """Handle center steering -- set state and send command via network."""
    state.steer = 90
    net.send_steering(90)
