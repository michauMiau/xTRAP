"""Input handling for Kivy RC client — keyboard, gamepad, and UI button input.

Replaces the original pygame version which used key.get_pressed() for steering.

In Kivy, input comes from:
1. Kivy widget bindings (buttons in UI panels) — handled by main.py button.on_press callbacks
2. Keyboard/gamepad events — handled here via Kivy's event system or SDL2 gamepad API

This module provides the high-level functions that buttons call to send commands.
"""

import logging
from network import CAR_ADDR, send_sock

log = logging.getLogger(__name__)


def _send_command(msg):
    """Send a command over UDP to the robot."""
    try:
        send_sock.sendto(msg.encode(), CAR_ADDR)
        log.debug(f"sent {msg}")
    except Exception as e:
        log.error(f"Error sending command '{msg}': {e}")


def send_steering(angle):
    """Send steering command to Cardputer.
    
    Args:
        angle: Steering angle in degrees (0 = full left, 180 = straight/center)
    """
    _send_command(f"S,{int(angle)}")


def send_throttle(throttle_value):
    """Send throttle command to Cardputer.
    
    Args:
        throttle_value: Throttle value (-100 = reverse/full brake, 0 = neutral, 100 = full forward)
    """
    _send_command(f"T,{int(throttle_value)}")
