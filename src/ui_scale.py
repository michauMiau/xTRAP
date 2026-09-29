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

# Upper bound. The raw ratio on a 1080px-short-side phone is 3.0, which is
# what we want — the button *widths* are now a fraction of the row (see
# BUTTON_SHARE below), so scaling up makes the touch targets bigger instead
# of overflowing the row they live in. Capped only to stop a 4K desktop
# monitor from producing absurd widgets.
MAX_SCALE = 3.0

# A single button may never take more than this share of its panel. The
# panels sit side by side, so the window width is split in two. Inert at the
# shares used today (largest is 0.36 for a display label), kept as a guard
# against a future share large enough to swallow the panel.
MAX_PANEL_SHARE = 0.40

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


def button_width(share):
    """Width for a touch button, as a share of the available panel width.

    The buttons used a fixed pixel width (scaled(45)), so on a high-resolution
    phone they stayed the same size while everything around them grew — that
    was the "buttons are still too small" report. A fraction of the panel
    instead means the buttons use the space they actually have.

    The panels sit side by side (MainLayout uses a 2-column grid), so a panel
    only ever gets half the window width.

    The width is the share, unconditionally. There is deliberately no
    minimum-size floor: at scale 3.0 a 96px touch target is 288px, wider than
    the 16% share (187px) it would be a floor for, so honouring it overflows
    the row and pushes the display label off screen. A button that fits beats
    a button that meets a size guideline. MAX_PANEL_SHARE stays as a guard so
    a future share of 1.0 cannot swallow the panel; on every screen this app
    targets the cap is inert, which the tests assert.
    """
    panel_width = Window.width / 2.0
    width = panel_width * share
    return int(round(min(width, panel_width * MAX_PANEL_SHARE)))


apply_density()

# Also pick up the environment override Kivy uses on some Android setups.
_ENV = os.environ.get("XTRAP_UI_SCALE")
if _ENV:
    try:
        _scale = float(_ENV)
    except ValueError:
        pass
