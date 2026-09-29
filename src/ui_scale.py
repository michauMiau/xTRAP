"""UI scale factor, shared by every widget module.

Kept separate from main.py so widgets can read the scale without importing
the app module (which would be a circular import: main imports widgets).

The sizes hardcoded in this project are authored for a 360dp-wide screen.
On a phone, a desktop window or a tablet they need scaling, so the factor
is derived from the current window size and stored here.
"""

import os

from kivy.core.window import Window

# Reference width the project's font/height values are written against.
REFERENCE_WIDTH = 360.0

# Upper bound. On a 1080px-short-side screen the raw ratio would be 3.0,
# which makes touch buttons taller than the row holding them. 1.8 keeps
# buttons usable while still scaling up on tablets and desktop.
MAX_SCALE = 1.8

# Only recompute when the short side actually changed — Window.size fires on
# every resize, and the panels read this during construction.
_scale = 1.0
_last_short_side = 0


def _compute_scale():
    """Scale factor for the current window's short side."""
    shortest = min(Window.width, Window.height)
    if shortest <= 0:
        return 1.0
    return max(1.0, min(shortest / REFERENCE_WIDTH, MAX_SCALE))


def apply_density():
    """Recompute the scale. Safe to call on every resize."""
    global _scale, _last_short_side  # pylint: disable=global-statement

    shortest = min(Window.width, Window.height)

    # Window size is 0 during early init on some platforms. Reset rather than
    # returning early, so a stale scale from a previous window cannot leak
    # into the new layout.
    if shortest <= 0:
        _last_short_side = 0
        _scale = 1.0
        return _scale

    if shortest == _last_short_side:
        return _scale

    _last_short_side = shortest
    _scale = _compute_scale()
    return _scale


def get_scale():
    """Current UI scale factor (1.0 = as authored)."""
    return _scale


def scaled(value):
    """Scale a font size, height or width by the current UI scale."""
    return int(round(value * _scale))


apply_density()

# Also pick up the environment override Kivy uses on some Android setups.
_ENV = os.environ.get("XTRAP_UI_SCALE")
if _ENV:
    try:
        _scale = float(_ENV)
    except ValueError:
        pass
