"""Tests for input handling — steering/throttle clamping and gamepad axis mapping.

These cover the pure logic in input.py. Kivy's Window is stubbed out so the
module imports without a display server (CI has no X11).
"""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def stub_kivy_window(monkeypatch):
    """input.py imports kivy.core.window at module load — stub just that module.

    The rest of Kivy stays real: settings.py needs kivy.config, and Kivy is
    installed in CI.
    """
    import types

    fake_window = types.ModuleType("kivy.core.window")

    class _Window:
        def bind(self, **kwargs):
            pass

        def unbind(self, **kwargs):
            pass

    fake_window.Window = _Window()
    monkeypatch.setitem(sys.modules, "kivy.core.window", fake_window)


@pytest.fixture
def sent(monkeypatch):
    """Capture steering/throttle messages instead of hitting the network."""
    import network as net

    out = {"steer": [], "throttle": []}
    monkeypatch.setattr(net, "send_steering", lambda a: out["steer"].append(a))
    monkeypatch.setattr(net, "send_throttle", lambda t: out["throttle"].append(t))
    return out


# --- set_throttle clamping ----------------------------------------------


def test_set_throttle_clamps_to_range(sent):
    import input as inp

    inp.set_throttle(150)
    assert sent["throttle"][-1] == 100

    inp.set_throttle(-150)
    assert sent["throttle"][-1] == -100


def test_set_throttle_accepts_bounds(sent):
    import input as inp

    inp.set_throttle(100)
    inp.set_throttle(-100)
    inp.set_throttle(0)
    assert sent["throttle"][-3:] == [100, -100, 0]


def test_release_throttle_sends_zero(sent):
    import input as inp

    inp.release_throttle()
    assert sent["throttle"][-1] == 0


# --- steering ------------------------------------------------------------


def test_release_steer_sends_center(sent):
    import input as inp

    inp.release_steer()
    assert sent["steer"][-1] == inp.center_steer


def test_set_steer_sends_int(sent):
    import input as inp

    inp.set_steer(angle=100.7)
    assert sent["steer"][-1] == 100
    assert isinstance(sent["steer"][-1], int)


# --- gamepad axis mapping ------------------------------------------------


def test_left_axis_full_left(sent):
    import input as inp

    inp.on_joy_axis(None, 0, 2, -1.0)
    assert sent["steer"][-1] == inp.left_steer


def test_left_axis_full_right(sent):
    import input as inp

    inp.on_joy_axis(None, 0, 2, 1.0)
    assert sent["steer"][-1] == inp.right_steer


def test_left_axis_center(sent):
    import input as inp

    inp.on_joy_axis(None, 0, 2, 0.0)
    assert sent["steer"][-1] == inp.center_steer


def test_raw_axis_values_are_normalized(sent):
    """Xbox pads report -32768..32767 — raw values must not leak through."""
    import input as inp

    inp.on_joy_axis(None, 0, 2, 32767)
    assert sent["steer"][-1] == inp.right_steer

    inp.on_joy_axis(None, 0, 2, -32768)
    assert sent["steer"][-1] == inp.left_steer


def test_deadzone_sends_center(sent):
    import input as inp

    inp.on_joy_axis(None, 0, 2, 0.05)
    assert sent["steer"][-1] == inp.center_steer


def test_right_trigger_forward(sent):
    import input as inp

    inp.on_joy_axis(None, 0, 5, 1.0)
    assert sent["throttle"][-1] == 100


def test_left_trigger_reverse(sent):
    import input as inp

    inp.on_joy_axis(None, 0, 4, -1.0)
    assert sent["throttle"][-1] == -100


def test_trigger_deadzone_sends_zero(sent):
    import input as inp

    inp.on_joy_axis(None, 0, 5, 0.05)
    assert sent["throttle"][-1] == 0

    inp.on_joy_axis(None, 0, 4, -0.05)
    assert sent["throttle"][-1] == 0


def test_unmapped_axis_is_ignored(sent):
    import input as inp

    before = (len(sent["steer"]), len(sent["throttle"]))
    inp.on_joy_axis(None, 0, 99, 1.0)
    assert (len(sent["steer"]), len(sent["throttle"])) == before
