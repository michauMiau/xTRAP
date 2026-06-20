"""Input handling for Kivy RC client -- keyboard, gamepad, and UI button input.

Replaces the original pygame version which used key.get_pressed() for steering.

In Kivy, input comes from:
1. Kivy widget bindings (buttons in UI panels) -- handled by main.py button.on_press callbacks
2. Keyboard/gamepad events -- handled here via Kivy's event system or SDL2 gamepad API

This module provides the high-level functions that buttons call to send commands.
"""

import logging
from state import state
import network as net

log = logging.getLogger(__name__)


def on_steer_left(*a):
    """Handle steering left -- set state and send command via network."""
    state.steer = 45
    net.send_steering(45)


def on_steer_right(*a):
    """Handle steering right -- set state and send command via network."""
    state.steer = 135
    net.send_steering(135)


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
        steering_panel: SteeringPanel instance with left_btn/right_btn
        throttle_panel: ThrottlePanel instance with reverse_btn/forward_btn
    """
    if steering_panel is None or throttle_panel is None:
        return

    # Wire steering buttons
    steering_panel.left_btn.bind(on_press=on_steer_left)
    steering_panel.right_btn.bind(on_press=on_steer_right)

    # Wire throttle buttons
    throttle_panel.reverse_btn.bind(on_press=on_throttle_reverse)
    throttle_panel.forward_btn.bind(on_press=on_throttle_forward)


def on_steer_center(*a):
    """Handle center steering -- set state and send command via network."""
    state.steer = 90
    net.send_steering(90)
