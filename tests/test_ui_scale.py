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
