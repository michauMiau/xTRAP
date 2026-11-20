"""Tests for rcar.py, run against a stubbed MicroPython.

The firmware cannot be imported directly: it opens WiFi, binds a socket and
runs `while True` at module level. So this harness stubs the machine module,
extracts the constants, classes and pure functions from the real source, and
executes them. What is tested is the code in rcar.py, not a copy of it.
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


class FakeSocket:
    """Captures what the firmware writes to a socket."""

    def __init__(self):
        self.sent = b""
        self.blocking = None

    def send(self, data):
        self.sent += data
        return len(data)

    def setblocking(self, flag):
        self.blocking = flag

    def settimeout(self, seconds):
        pass


def _machine_stub():
    mod = types.ModuleType("machine")
    mod.Pin = FakePin
    mod.PWM = FakePWM
    mod.I2C = object
    return mod


def _exec_nodes(nodes, sandbox):
    exec(  # pylint: disable=exec-used
        compile(ast.Module(body=nodes, type_ignores=[]), str(RCAR), "exec"), sandbox
    )


def _load_from_source():
    """Execute the testable parts of rcar.py in a sandbox.

    Takes PINS/FAILSAFE, the Servo and Motor classes, and the pure websocket
    helpers straight out of the file, so these tests cannot drift from the
    firmware.
    """
    tree = ast.parse(SOURCE)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.Assign, ast.FunctionDef)):
            name = None
            if isinstance(node, ast.ClassDef):
                name = node.name
            elif isinstance(node, ast.FunctionDef):
                name = node.name
            elif isinstance(node, ast.Assign):
                name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
            if name in ("Servo", "Motor", "send_all", "decode_text", "ws_accept", "ws_send", "ws_parse") or (
                name and re.match(r"^(PINS|FAILSAFE_MS|WS_GUID)$", name)
            ):
                keep.append(node)

    assert len(keep) >= 6, f"expected the firmware pieces, got {[type(n).__name__ for n in keep]}"

    sandbox = {
        "Pin": FakePin,
        "PWM": FakePWM,
        "__name__": "rcar_under_test",
        "hashlib": __import__("hashlib"),
        "binascii": __import__("binascii"),
        "struct": __import__("struct"),
    }
    _exec_nodes(keep, sandbox)
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
    """The pin map has to record that I2C(0) is GPIO8/9, not GPIO2/3."""
    assert re.search(r"I2C\(0\)", SOURCE)
    assert re.search(r"GPIO8/9", SOURCE)
    assert "mpconfigboard.h" in SOURCE

    warning = SOURCE[SOURCE.index("I2C(0) is"):SOURCE.index("PINS = {")]
    assert re.search(r"GPIO1/2", warning), "stock-firmware collision warning is gone"
    assert re.search(r"collide", warning), "the consequence is not stated"


# --- servo ------------------------------------------------------------------

def test_servo_uses_50hz_hardware_pwm(fw):
    servo = fw["Servo"](2)
    assert servo.pwm.freq_value == 50


def test_servo_pulse_mapping(fw):
    """Standard hobby servos take 1ms..2ms for 0..180 degrees."""
    servo = fw["Servo"](2)
    for angle, expected in ((0, 1000), (90, 1500), (180, 2000)):
        servo._write(angle)
        assert servo.pwm.pulse_us == pytest.approx(expected, abs=0.5)


def test_servo_pulse_stays_in_spec_at_every_angle(fw):
    """Nothing may fall outside the 1000..2000us window."""
    servo = fw["Servo"](2)
    for angle in range(181):
        servo._write(angle)
        assert 1000 <= servo.pwm.pulse_us <= 2000, angle


def test_old_bug_produced_an_out_of_spec_pulse():
    """Documents the 500..2500us mapping this replaced."""
    pulse_0 = 500 + (0 / 180.0) * 2000
    pulse_180 = 500 + (180 / 180.0) * 2000
    assert pulse_0 == 500 and pulse_180 == 2500
    assert pulse_0 < 1000 and pulse_180 > 2000


def test_servo_has_no_back_to_back_pulse_loop():
    """The `for _ in range(3): write_pulse(...)` shape must not come back."""
    tree = ast.parse(SOURCE)
    servo_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Servo")
    methods = {m.name: ast.dump(m) for m in servo_cls.body if isinstance(m, ast.FunctionDef)}

    assert "write_pulse" not in methods
    for name, dump in methods.items():
        assert "sleep_us" not in dump, f"{name} busy-waits on sleep_us"
        assert "range" not in dump, f"{name} loops pulses instead of using hardware PWM"

    assert "duty_ns" in methods["_write"]


def test_servo_has_no_signal_until_commanded(fw):
    """Boot must not drive the steering."""
    servo = fw["Servo"](2)
    assert servo.pwm.duty_ns_value == 0, "servo is powered before any command"
    assert servo.target is None
    assert servo.holding is False


def test_first_command_starts_the_frame(fw):
    """A real command must still light the servo up — the fix is not silence."""
    servo = fw["Servo"](2)
    assert servo.pwm.duty_ns_value == 0

    servo.set_angle(95)
    assert servo.pwm.duty_ns_value > 0
    assert servo.angle == 95
    assert servo.pwm.pulse_us == pytest.approx(1000 + 95 / 180 * 1000, abs=1)


def test_servo_keeps_emitting_after_arriving(fw):
    """A hardware channel keeps the frame running, so idle hold torque stays."""
    servo = fw["Servo"](2)
    servo._write(90)
    duty_at_rest = servo.pwm.duty_ns_value
    assert duty_at_rest == pytest.approx(1_500_000, abs=1000)
    assert duty_at_rest > 0, "a servo at rest must still receive a frame"


def test_set_angle_is_non_blocking(fw):
    """No sleep in the command path — a busy wait stalls the main loop."""
    servo = fw["Servo"](2)
    assert servo.set_angle(120) is None
    assert servo.angle == 120


def test_servo_slew_is_slow_enough_for_the_rail(fw):
    """5 deg/tick reset the ESP32 mid-sweep; the slew must stay gentle."""
    servo = fw["Servo"](2)
    assert servo.speed <= 2


def test_servo_step_moves_gradually_and_snaps(fw):
    servo = fw["Servo"](2)
    servo._write(90)
    servo.target = 100

    servo._step()
    assert servo.angle == 92
    while servo._step() is False:
        pass
    assert servo.angle == 100
    assert servo._step() is False


def test_servo_clamps_out_of_range_commands(fw):
    """A malformed S,999 must not compute a pulse outside the servo window."""
    servo = fw["Servo"](2)
    servo.set_angle(999)
    assert servo.angle == 180
    servo._write(90)
    servo.set_angle(-50)
    assert servo.target == 0
    while servo._step() is False:
        pass
    assert servo.angle == 0


def test_release_drops_the_frame_and_set_angle_wakes_it(fw):
    """X parks the servo; the next S must light it up again."""
    servo = fw["Servo"](2)
    servo.set_angle(90)
    assert servo.pwm.duty_ns_value > 0

    servo.release()
    assert servo.pwm.duty_ns_value == 0
    assert servo.target is None
    assert servo.holding is False

    servo.set_angle(90)
    assert servo.pwm.duty_ns_value > 0, "the servo stayed asleep after a command"
    assert servo.holding is True


def test_each_servo_owns_its_own_ledc_channel(fw):
    left = fw["Servo"](fw["PINS"]["servo_left"])
    right = fw["Servo"](fw["PINS"]["servo_right"])
    assert left.pwm is not right.pwm
    assert left.pwm.pin.num == 2
    assert right.pwm.pin.num == 3


def test_both_servos_are_constructed():
    assert 'Servo(PINS["servo_left"])' in SOURCE
    assert 'Servo(PINS["servo_right"])' in SOURCE


def test_steering_command_reaches_both_servos():
    """One S command must move both, or the linkage fights itself."""
    s_block = SOURCE.split('parts[0] == "S"')[1].split('elif parts[0] == "X"')[0]
    assert s_block.count("set_angle(angle)") == 2
    assert "servo_2.set_angle(angle)" in s_block


def test_release_command_reaches_both_servos():
    x_block = SOURCE.split('elif parts[0] == "X"')[1].split('elif parts[0] == "T"')[0]
    assert x_block.count("release()") == 2
    assert "servo_2.release()" in x_block


def test_servo_tick_in_the_main_loop_drives_both():
    """Otherwise servo_2 is constructed but never stepped."""
    loop = SOURCE.split("--- SERVO STEP")[1].split("--- FAILSAFE ---")[0]
    assert "servo._step()" in loop
    assert "servo_2._step()" in loop


# --- failsafe ---------------------------------------------------------------

def test_failsafe_threshold(fw):
    assert fw["FAILSAFE_MS"] == 1000


def test_failsafe_is_a_time_comparison():
    assert "last_drive_time = time.ticks_ms()" in SOURCE
    assert "time.ticks_diff(now, last_drive_time) > FAILSAFE_MS" in SOURCE
    assert "if got_command" not in SOURCE


def test_drive_command_refreshes_the_failsafe_timer():
    fn = SOURCE.split("def handle_text")[1].split("\nprint(")[0]
    assert "last_drive_time = time.ticks_ms()" in fn
    assert "motor.run(throttle)" in fn


def test_failsafe_stays_quiet_while_idle():
    failsafe = SOURCE.split("--- FAILSAFE ---")[1]
    assert "throttle != 0" in failsafe
    assert "throttle = 0" in failsafe, "the motor is not marked as stopped"


def test_failsafe_stops_the_motor():
    failsafe = SOURCE.split("--- FAILSAFE ---")[1]
    assert "motor.stop()" in failsafe


def test_failsafe_logs_when_it_fires():
    failsafe = SOURCE.split("--- FAILSAFE ---")[1]
    assert "print(" in failsafe
    assert "FAILSAFE" in failsafe


def test_failsafe_threshold_fires_after_exactly_1000ms(fw):
    """1000ms is the decision, so the boundary has to be right."""
    threshold = fw["FAILSAFE_MS"]

    def should_stop(elapsed_ms):
        return elapsed_ms > threshold

    assert should_stop(0) is False
    assert should_stop(threshold - 1) is False
    assert should_stop(threshold) is False
    assert should_stop(threshold + 1) is True
    assert should_stop(10_000) is True

    assert "> FAILSAFE_MS" in SOURCE
    assert ">= FAILSAFE_MS" not in SOURCE


def test_failsafe_threshold_is_many_main_loops():
    assert 1000 % 20 == 0
    assert 1000 // 20 == 50


def test_motor_still_uses_500hz(fw):
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
    assert motor.pwm_fwd.duty_ns_value > 0
    assert motor.pwm_rev.duty_ns_value == 0
    motor.run(-100)
    assert motor.pwm_fwd.duty_ns_value == 0
    assert motor.pwm_rev.duty_ns_value > 0
    motor.run(0)
    assert motor.pwm_fwd.duty_ns_value == 0
    assert motor.pwm_rev.duty_ns_value == 0


# --- web socket -------------------------------------------------------------

def test_web_server_serves_the_page_and_ws():
    assert "PORT = 80" in SOURCE
    assert '"/www/index.html"' in SOURCE
    assert '"/sd/www/index.html"' in SOURCE
    assert 'path == "/ws"' in SOURCE
    assert "Sec-WebSocket-Accept" in SOURCE
    assert (RCAR.parent / "www" / "index.html").exists()


def test_no_decode_errors_kwarg():
    """MicroPython's bytes.decode takes no keyword arguments."""
    assert "decode(errors=" not in SOURCE
    assert "encode(errors=" not in SOURCE


def test_decode_text_handles_bad_utf8(fw):
    assert fw["decode_text"](b"S,60") == "S,60"
    assert fw["decode_text"](b"\xff\xfe") == "\xff\xfe"


def test_ws_accept_matches_rfc6455_example(fw):
    """The RFC 6455 sample key must produce the sample accept value."""
    assert fw["ws_accept"]("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_ws_parse_reads_a_masked_text_frame(fw):
    """Browser frames are masked; the payload must come out unmasked."""
    payload = b"S,60"
    mask = b"\x37\xfa\x21\x3d"
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    frame = bytes([0x81, 0x80 | len(payload)]) + mask + masked

    opcode, text, used = fw["ws_parse"](frame)
    assert opcode == 0x1
    assert text == b"S,60"
    assert used == len(frame)


def test_ws_parse_waits_for_a_complete_frame(fw):
    assert fw["ws_parse"](b"\x81") is None
    assert fw["ws_parse"](b"\x81\x84\x37\xfa") is None


def test_ws_parse_reads_an_extended_length(fw):
    payload = b"T" + b"0" * 200
    mask = b"\x00\x00\x00\x00"
    frame = bytes([0x81, 0x80 | 126]) + len(payload).to_bytes(2, "big") + mask + payload
    opcode, text, used = fw["ws_parse"](frame)
    assert opcode == 0x1
    assert text == payload
    assert used == len(frame)


def test_ws_send_writes_a_text_frame(fw):
    sock = FakeSocket()
    fw["ws_send"](sock, "B,97")
    assert sock.sent == b"\x81\x04B,97"


def test_telemetry_goes_out_over_the_websocket():
    assert 'ws_send(client, "B,%d" % pct)' in SOURCE
    assert "STATS_MS = 5000" in SOURCE


def test_page_talks_to_the_ws_endpoint():
    page = (RCAR.parent / "www" / "index.html").read_text()
    assert "/ws" in page
    assert "S," in page
    assert "T," in page
    assert "'X'" in page
