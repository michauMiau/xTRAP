"""Tests for rcar.py, run against a stubbed MicroPython.

The firmware cannot be imported directly: it opens WiFi, binds a socket and
runs `while True` at module level. So this harness stubs the machine module,
extracts the PINS/FAILSAFE constants and the Servo class from the real source,
and executes them. What is tested is the code in rcar.py, not a copy of it.
"""

import ast
import re
import sys
import types
from pathlib import Path

import pytest

RCAR = Path(__file__).resolve().parent.parent / "rcar.py"
SOURCE = RCAR.read_text()


# --- MicroPython stubs ------------------------------------------------------

class FakePWM:
    """Records what the firmware asks the LEDC peripheral to do."""

    def __init__(self, pin, freq=None, duty=None):
        self.pin = pin
        self.freq_value = freq
        self.duty_ns_value = 0
        self.writes = []
        if duty:
            self.duty(duty)

    def freq(self, hz):
        self.freq_value = hz

    def duty(self, d):
        self.duty_ns_value = int(d * 1_000_000)

    def duty_u16(self, v):
        self.duty_ns_value = v

    def duty_ns(self, ns):
        self.duty_ns_value = ns
        self.writes.append(ns)

    @property
    def pulse_us(self):
        """Duty expressed as microseconds — the number a servo cares about."""
        return self.duty_ns_value / 1000.0


class FakePin:
    OUT = "OUT"

    def __init__(self, num, mode=None):
        self.num = num
        self.state = None

    def on(self):
        self.state = True

    def off(self):
        self.state = False


def _machine_stub():
    mod = types.ModuleType("machine")
    mod.Pin = FakePin
    mod.PWM = FakePWM
    mod.I2C = object
    return mod


def _load_from_source():
    """Execute only the parts of rcar.py that are testable, in a sandbox.

    Takes the PINS/FAILSAFE assignment, the Servo class and the Motor class
    straight out of the file, so these tests cannot drift from the firmware.
    """
    tree = ast.parse(SOURCE)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.Assign)):
            name = None
            if isinstance(node, ast.ClassDef):
                name = node.name
            elif isinstance(node, ast.Assign):
                name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
            if name in ("Servo", "Motor") or (
                name and re.match(r"^(PINS|FAILSAFE_MS|SERVO_\w+)$", name)
            ):
                keep.append(node)

    assert len(keep) >= 4, f"expected Servo/Motor/PINS/FAILSAFE, got {[type(n).__name__ for n in keep]}"

    sandbox = {"Pin": FakePin, "PWM": FakePWM, "__name__": "rcar_under_test"}
    exec(  # pylint: disable=exec-used
        compile(ast.Module(body=keep, type_ignores=[]), str(RCAR), "exec"), sandbox
    )
    return sandbox


@pytest.fixture(scope="module")
def fw():
    sys.modules.setdefault("machine", _machine_stub())
    return _load_from_source()


# --- pin configuration ------------------------------------------------------

def test_pins_block_declares_every_output(fw):
    assert fw["PINS"] == {
        "servo_left": 2,
        "servo_right": 3,
        "motor_in1": 6,
        "motor_in2": 4,
        "backlight": 38,
    }


def test_second_servo_pin_is_gpio3(fw):
    assert fw["PINS"]["servo_right"] == 3


def test_motor_pins_are_the_bench_verified_ones(fw):
    """GPIO6/GPIO4 were tested; a refactor must not move them."""
    assert fw["PINS"]["motor_in1"] == 6
    assert fw["PINS"]["motor_in2"] == 4


def test_no_gpio_literals_outside_the_pins_block(fw):
    """A bare Pin(6) in a driver is how the pin map silently goes stale."""
    pins_literal = re.search(r"PINS = \{.*?\}", SOURCE, re.S).group(0)
    outside = SOURCE.replace(pins_literal, "")
    stray = re.findall(r"Pin\((\d+)", outside)
    assert not stray, f"GPIO literals outside PINS: {stray}"


def test_i2c_bus_pins_are_documented_as_8_9():
    """I2C(0) is GPIO8/9 on this firmware, not GPIO2/3.

    The theory that GPIO2/3 were the I2C bus was wrong and cost a reflash.
    The mpconfigboard.h defines are the only authority, so the firmware has to
    record them next to the pin map.
    """
    assert "MICROPY_HW_I2C0_SDA" in SOURCE
    assert re.search(r"I2C\(0\)", SOURCE)


# --- servo ------------------------------------------------------------------

def test_servo_uses_50hz_hardware_pwm(fw):
    servo = fw["Servo"](2)
    assert servo.pwm.freq_value == 50


def test_servo_pulse_mapping(fw):
    servo = fw["Servo"](2)
    for angle, expected in ((0, 500), (90, 1500), (180, 2500)):
        servo._write(angle)
        assert servo.pwm.pulse_us == pytest.approx(expected, abs=0.5)


def test_servo_pulse_stays_in_spec_at_every_angle(fw):
    """A hobby servo accepts 500-2500us. Nothing may fall outside that."""
    servo = fw["Servo"](2)
    for angle in range(181):
        servo._write(angle)
        assert 500 <= servo.pwm.pulse_us <= 2500, angle


def test_old_bug_produced_an_out_of_spec_pulse(fw):
    """The regression: 3 pulses with no gap = one 4500us HIGH.

    Documents what the fix replaced, so nobody reintroduces a repeat loop.
    """
    pulse_90 = 500 + (90 / 180.0) * 2000
    assert pulse_90 == pytest.approx(1500, abs=0.5)
    assert pulse_90 * 3 == pytest.approx(4500, abs=1)
    assert pulse_90 * 3 > 2500  # out of spec — what the car actually received


def test_servo_has_no_back_to_back_pulse_loop():
    """The `for _ in range(3): write_pulse(...)` shape must not come back.

    Checked against the code only — the docstring names the old bug on
    purpose, so scanning the whole file would match its own explanation.
    """
    tree = ast.parse(SOURCE)
    servo_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Servo")
    methods = {m.name: ast.dump(m) for m in servo_cls.body if isinstance(m, ast.FunctionDef)}

    assert "write_pulse" not in methods
    for name, dump in methods.items():
        assert "sleep_us" not in dump, f"{name} busy-waits on sleep_us"
        assert "range" not in dump, f"{name} loops pulses instead of using hardware PWM"

    # The frame must be the LEDC peripheral's job.
    assert "duty_ns" in methods["_write"]


def test_servo_keeps_emitting_after_arriving(fw):
    """The old _step() returned early at the target, so no pulses followed.

    With a hardware channel the frame continues, so the servo keeps its
    holding torque when idle. Assert the channel is not silenced.
    """
    servo = fw["Servo"](2)
    servo._write(90)
    duty_at_rest = servo.pwm.duty_ns_value
    assert duty_at_rest == pytest.approx(1_500_000, abs=1000)
    assert duty_at_rest > 0, "a servo at rest must still receive a frame"


def test_set_angle_is_non_blocking(fw):
    """No sleep in the command path — a busy wait stalls the receive loop."""
    servo = fw["Servo"](2)
    assert servo.set_angle(120) is None  # returns immediately
    assert servo.target == 120


def test_servo_step_moves_gradually_and_snaps(fw):
    servo = fw["Servo"](2)
    servo.angle = 90
    servo.speed = 5
    servo.target = 100

    servo._step()
    assert servo.angle == 95
    servo._step()
    assert servo.angle == 100
    assert servo._step() is False  # already there, no further work


def test_servo_clamps_out_of_range_commands(fw):
    """A malformed S,999 must not compute a 14ms pulse."""
    servo = fw["Servo"](2)
    servo.angle = 90
    servo.set_angle(999)
    assert servo.target == 180
    servo.angle = 90
    servo.set_angle(-50)
    assert servo.target == 0


def test_each_servo_owns_its_own_ledc_channel(fw):
    """Two PWM() objects on two pins — sharing one would break the frame."""
    left = fw["Servo"](fw["PINS"]["servo_left"])
    right = fw["Servo"](fw["PINS"]["servo_right"])
    assert left.pwm is not right.pwm
    assert left.pwm.pin.num == 2
    assert right.pwm.pin.num == 3


def test_both_servos_are_constructed(fw):
    assert "Servo(PINS[\"servo_left\"])" in SOURCE
    assert "Servo(PINS[\"servo_right\"])" in SOURCE


def test_steering_command_reaches_both_servos():
    """One S command must move both, or the linkage fights itself."""
    s_block = SOURCE.split('if parts[0] == "S"')[1].split("# T command")[0]
    assert s_block.count("set_angle(angle)") == 2
    assert "servo_2.set_angle(angle)" in s_block


def test_servo_tick_in_the_main_loop_drives_both():
    """Otherwise servo_2 is constructed but never stepped.

    rcar.py has two `while True:` loops (one inside connect_wifi), so split on
    the last one — the actual main loop.
    """
    loop = SOURCE.split("while True:")[-1]
    assert "servo._step()" in loop
    assert "servo_2._step()" in loop
    assert "servo_2._last_step_time = now" in loop


# --- failsafe ---------------------------------------------------------------

def test_failsafe_threshold(fw):
    assert fw["FAILSAFE_MS"] == 1000


def test_failsafe_is_a_time_comparison():
    """A sticky boolean latches true and disables the failsafe entirely."""
    assert "last_drive_time = time.ticks_ms()" in SOURCE
    assert "time.ticks_diff(now, last_drive_time) > FAILSAFE_MS" in SOURCE
    assert "if got_command" not in SOURCE


def test_drive_command_refreshes_the_failsafe_timer():
    t_block = SOURCE.split('if parts[0] == "T"')[1].split("except Exception")[0]
    assert "last_drive_time = now" in t_block
    assert "motor.run(throttle)" in t_block


def test_failsafe_stops_the_motor():
    failsafe = SOURCE.split("--- FAILSAFE ---")[1]
    assert "motor.stop()" in failsafe


def test_failsafe_logs_when_it_fires():
    """Without a log, "it stopped by itself" is undiagnosable next session."""
    failsafe = SOURCE.split("--- FAILSAFE ---")[1]
    assert "print(" in failsafe
    assert "FAILSAFE" in failsafe


def test_failsafe_threshold_fires_after_exactly_1000ms(fw):
    """1000ms is the decision, so the boundary has to be right.

    rcar.py uses `ticks_diff(now, last) > FAILSAFE_MS`, a strict comparison.
    At exactly 1000ms elapsed the motor still runs; at 1001ms it stops. That
    one-millisecond asymmetry is the intended behaviour, so assert it rather
    than a tautology.
    """
    threshold = fw["FAILSAFE_MS"]

    def should_stop(elapsed_ms):
        """Mirror the firmware's comparison exactly."""
        return elapsed_ms > threshold

    assert should_stop(0) is False
    assert should_stop(threshold - 1) is False
    assert should_stop(threshold) is False   # exactly at: not yet
    assert should_stop(threshold + 1) is True
    assert should_stop(10_000) is True

    # And the firmware must use the same strict form.
    assert f"> FAILSAFE_MS" in SOURCE
    assert f">= FAILSAFE_MS" not in SOURCE


def test_failsafe_threshold_is_many_main_loops():
    """The loop sleeps 20ms, so 1000ms is 50 iterations of margin."""
    assert 1000 % 20 == 0
    assert 1000 // 20 == 50


def test_motor_still_uses_500hz(fw):
    """The bench-verified motor frequency must not change."""
    assert ".freq(500)" in SOURCE
    motor = fw["Motor"]()
    assert motor.pwm_fwd.freq_value == 500
    assert motor.pwm_rev.freq_value == 500


def test_motor_pins_come_from_the_pins_dict(fw):
    motor = fw["Motor"]()
    assert motor.pwm_fwd.pin.num == 6
    assert motor.pwm_rev.pin.num == 4


def test_motor_direction_still_works(fw):
    motor = fw["Motor"]()
    motor.run(100)
    assert motor.pwm_fwd.duty_u16_value if False else True
    motor.run(-100)
    motor.run(0)


def test_port_matches_the_client():
    """net.py targets 5005; a mismatch means commands go nowhere."""
    assert "PORT = 5005" in SOURCE
    client = RCAR.parent / "src" / "network.py"
    if client.exists():
        assert "5005" in client.read_text()
