"""Tests for the UI scale factor.

The app was unusable on a phone: RCControlCenterApp.__init__ clamped the
window to 200px tall (`min(800, w), min(200, h)`), so every panel was
squeezed into a letterbox. These tests pin the scaling rules so that clamp
cannot come back unnoticed.
"""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def fake_window(monkeypatch):
    """ui_scale reads kivy.core.window at import time — stub it."""
    import types

    fake = types.ModuleType("kivy.core.window")
    fake.Window = types.SimpleNamespace(width=1080, height=1080)
    monkeypatch.setitem(sys.modules, "kivy.core.window", fake)
    return fake


@pytest.fixture(autouse=True)
def fresh_module(fake_window, monkeypatch):
    """Reload ui_scale with a controlled window size per test."""
    import importlib

    import ui_scale

    return importlib.reload(ui_scale), fake_window


def _set_window(fake_window, width, height):
    fake_window.Window.width = width
    fake_window.Window.height = height


def test_scale_is_one_on_reference_width(fresh_module):
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 360, 360)
    assert ui_scale.apply_density() == pytest.approx(1.0)


def test_scale_never_drops_below_one(fresh_module):
    """A small window must not shrink touch targets below the authored size."""
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 200, 200)
    assert ui_scale.apply_density() == pytest.approx(1.0)


def test_scale_is_capped(fresh_module):
    """Without a cap a 1080px screen gives 3.0 and the buttons overflow."""
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 1080, 1080)
    assert ui_scale.apply_density() == pytest.approx(ui_scale.MAX_SCALE)


def test_landscape_phone_scales_up(fresh_module):
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 2340, 1080)
    scale = ui_scale.apply_density()
    assert scale > 1.0
    assert scale <= ui_scale.MAX_SCALE


def test_shorter_side_drives_the_scale(fresh_module):
    """Portrait and landscape of the same phone must scale identically."""
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 1080, 2340)
    portrait = ui_scale.apply_density()
    _set_window(fake_window, 2340, 1080)
    assert ui_scale.apply_density() == pytest.approx(portrait)


def test_sized_scales_fonts_and_buttons(fresh_module):
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 720, 720)
    ui_scale.apply_density()
    # authored 32px button font, 45px width
    assert ui_scale.scaled(32) > 32
    assert ui_scale.scaled(45) > 45
    assert isinstance(ui_scale.scaled(32), int)


def test_scaled_is_identity_at_scale_one(fresh_module):
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 360, 360)
    ui_scale.apply_density()
    assert ui_scale.scaled(18) == 18


def test_zero_size_window_does_not_crash(fresh_module):
    """Window size is 0 during early init on some platforms."""
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 0, 0)
    assert ui_scale.apply_density() == pytest.approx(1.0)
    assert ui_scale.scaled(32) == 32


def test_app_does_not_clamp_window_height(fresh_module):
    """The 200px clamp that broke the phone layout must not reappear."""
    import inspect

    import main

    source = inspect.getsource(main.RCControlCenterApp.__init__)
    assert "min(200" not in source
    assert "Window.size" not in source


# --- button_width -----------------------------------------------------------
#
# The buttons were a fixed scaled(45) wide, so on a 2K phone they stayed the
# same size while everything around them grew — "buttons are still too small
# for use on a 2k res phone". They are now a share of the panel.

# width, height, label
SCREENS = [
    (2340, 1080, "2k landscape"),
    (2400, 1080, "fhd+ wide"),
    (1440, 3120, "qhd+ tall"),
    (1280, 720, "720p"),
    (1920, 1080, "desktop 1080"),
    (800, 600, "small window"),
    (1080, 2340, "2k portrait"),
]

# The shares used by SteeringPanel and ThrottlePanel in src/main.py.
STEERING_ROW = [0.16, 0.16, 0.16, 0.32]
THROTTLE_ROW = [0.20, 0.36, 0.20]
ALL_SHARES = STEERING_ROW + THROTTLE_ROW


@pytest.mark.parametrize("width,height,label", SCREENS)
def test_control_rows_fit_their_panel(fresh_module, width, height, label):
    """Neither control row may be wider than the half-panel it lives in."""
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, width, height)
    ui_scale.apply_density()

    panel = width / 2.0
    for row in (STEERING_ROW, THROTTLE_ROW):
        total = sum(ui_scale.button_width(share) for share in row)
        assert total <= panel, label


@pytest.mark.parametrize("width,height,label", SCREENS)
def test_button_width_is_exactly_the_share(fresh_module, width, height, label):
    """Width == panel share, and the cap is inert.

    Asserting the exact value (not just <= ceiling) is what makes raising
    MAX_PANEL_SHARE fail here instead of silently passing while letting a
    button swallow the panel.
    """
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, width, height)
    ui_scale.apply_density()

    panel = width / 2.0
    for share in ALL_SHARES:
        assert ui_scale.button_width(share) == pytest.approx(panel * share, abs=2), label
    assert max(ALL_SHARES) < ui_scale.MAX_PANEL_SHARE


def test_buttons_grow_with_the_screen(fresh_module):
    """The reported regression: buttons were fixed pixel widths."""
    ui_scale, fake_window = fresh_module

    _set_window(fake_window, 1280, 720)
    ui_scale.apply_density()
    small = ui_scale.button_width(0.16)

    _set_window(fake_window, 2340, 1080)
    ui_scale.apply_density()
    large = ui_scale.button_width(0.16)

    assert large > small
    # A fixed scaled(45) at 720p (scale 2.0) is 90px; the share is 102px.
    # At 2K the fixed width would still be 135px while the share is 187px.
    assert large == pytest.approx((2340 / 2.0) * 0.16, abs=2)


def test_buttons_are_bigger_than_the_old_fixed_width_on_2k(fresh_module):
    """On a 2K phone the button must be wider than the 45px authored width.

    This is the concrete assertion for the report: previously every screen
    produced scaled(45) = 135px, so nothing grew with resolution.
    """
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 2340, 1080)
    ui_scale.apply_density()

    assert ui_scale.button_width(0.16) > ui_scale.scaled(45)


def test_no_minimum_floor_forces_overflow(fresh_module):
    """A minimum-size floor must not be re-added as an absolute pixel value.

    Android's guidance is ~48dp and the old floor was 96px; scaled to 3.0
    that is 288px, far wider than the 16% share (187px) of a 1170px panel.
    Reinstating it as a floor overflows the row and pushes the steering
    display label off screen.
    """
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 2340, 1080)
    ui_scale.apply_density()

    panel = 2340 / 2.0
    assert ui_scale.scaled(96) > panel * 0.16  # the trap
    assert ui_scale.button_width(0.16) < panel
    assert not hasattr(ui_scale, "MIN_TOUCH")


def test_max_scale_reaches_full_2k_density(fresh_module):
    """MAX_SCALE must not cap below the 2K phone's own ratio.

    Regression guard: MAX_SCALE was 1.8, which held a 1080px-short-side phone
    at scale 1.8 instead of 3.0 and left the buttons too small. The cap now
    has to admit the raw ratio on every screen this app targets.
    """
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 2340, 1080)
    assert ui_scale.apply_density() == pytest.approx(3.0, abs=0.01)

    _set_window(fake_window, 1440, 3120)
    ui_scale._last_short_side = 0
    assert ui_scale.apply_density() == pytest.approx(3.0, abs=0.01)

    assert ui_scale.MAX_SCALE >= min(1080 / ui_scale.REFERENCE_WIDTH, 3.0)


def test_max_panel_share_cap_is_load_bearing(fresh_module):
    """MAX_PANEL_SHARE has to actually clamp a share that is too large.

    The oversized share is a fixed number, not CAP + 0.2: deriving it from the
    constant made this test pass with the cap set to 0.90, which is exactly
    the kind of self-referential assertion that verifies nothing.
    """
    ui_scale, fake_window = fresh_module
    _set_window(fake_window, 2340, 1080)
    ui_scale.apply_density()

    panel = 2340 / 2.0
    assert ui_scale.MAX_PANEL_SHARE <= 0.40  # in practice never reached
    assert ui_scale.button_width(0.95) == pytest.approx(panel * 0.40, abs=2)
    assert ui_scale.button_width(0.95) < panel * 0.95


def test_source_shares_match_the_panels(fresh_module):
    """The shares in these tests must be the ones src/main.py actually uses.

    The rows above are hand-copied. If someone changes a share in main.py
    without updating them, the panel-fit tests stop testing the real layout.
    """
    import inspect
    import re

    import main

    source = inspect.getsource(main)
    used = sorted(float(m) for m in re.findall(r"button_width\(([\d.]+)\)", source))

    assert used == sorted(ALL_SHARES)
