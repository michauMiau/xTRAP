"""xTRAP car firmware — MicroHydra app.

The Cardputer screen shows the car's address, battery, steering and link
state while it runs; the browser remote connects to ws://<car-ip>/ws and
drives it. ENT releases the steering servos, SPC stops the motor, ESC
recenters the steering.
"""
from lib import display
from lib import userinput
from lib.battlevel import Battery
from lib.hydra.config import Config
from lib.userinput import bmi270
from machine import I2C, Pin, PWM
import binascii
import hashlib
import network
import select
import socket
import struct
import time
import gc

batt = Battery()
pct = batt.read_pct()

# --- PINS ---
# Every output in one place, so a rewiring is a diff here and not a hunt
# through the driver classes.
#
# I2C(0) is GPIO8/9 on this firmware, per MicroHydra's mpconfigboard.h. Do not
# infer bus pins from a bus number: the stock Cardputer firmware maps I2C(0)
# to GPIO1/2, which would collide with servo_left.
PINS = {
    "servo_left":  2,
    "servo_right": 3,
    "motor_in1":   6,   # MX1508 IN1 — forward PWM
    "motor_in2":   4,   # MX1508 IN2 — reverse PWM
    "backlight":   38,
}

# Stop the motor when no throttle command has arrived for this long. The main
# loop runs every ~20ms, so 1000ms is 50 iterations of margin.
FAILSAFE_MS = 1000

PORT = 80
# The page can live on the internal flash (/www) or on the SD card (/sd/www),
# depending on where it was copied.
PAGE_PATHS = ("/www/index.html", "/sd/www/index.html")
STATS_MS = 5000

# --- MICROHYDRA UI ---
DISPLAY = display.Display()
INPUT = userinput.UserInput()
CONFIG = Config()

# --- WIFI ---
nic = network.WLAN(network.STA_IF)
nic.config(pm=0)


def connect_wifi():
    if not nic.active():
        nic.active(True)

    if not nic.isconnected():
        while True:
            try:
                nic.connect(CONFIG['wifi_ssid'], CONFIG['wifi_pass'])
                break
            except Exception:
                time.sleep_ms(500)

        while not nic.isconnected():
            time.sleep_ms(500)

    print("Connected:", nic.ifconfig())


def wifi_rssi():
    """Signal strength in dBm, or None when the driver will not say."""
    try:
        return nic.status('rssi')
    except Exception:
        return None


def rssi_bars(rssi):
    """0..4 bars from a dBm value (-30 strong, -90 gone)."""
    if rssi is None:
        return "?"
    level = (rssi + 90) * 4 // 60
    return "#" * max(0, min(4, level))


# --- IMU Setup ---
i2c = I2C(0)
imu = bmi270.BMI270(i2c)


def read_accel():
    try:
        ax, ay, az = imu.acceleration
        return ax, ay, az
    except Exception:
        return 0.0, 0.0, 0.0


# --- SERVO (smooth non-blocking via main-loop time check) ---


class Servo:
    """Steering servo on hardware PWM.

    A servo needs a continuous 20ms frame, not a burst of pulses: without
    one it has no holding torque and sags. So the 50Hz frame is left running
    on the LEDC peripheral and set_angle() only changes the duty.
    """

    def __init__(self, pin):
        # 50Hz frame, no duty until the first command arrives. A servo needs a
        # frame to hold position, but it must not be given one it never asked
        # for — that drives it to the default angle on boot.
        self.pwm = PWM(Pin(pin), freq=50, duty=0)
        self.angle = 90
        self.target = None
        self.holding = False
        # Degrees per main-loop tick (20ms). At 5 it slewed ~250 deg/s, which
        # pulled enough stall current through the steering linkage to sag the
        # battery rail and reset the ESP32 while sweeping. 2 keeps the slew
        # inside ~100 deg/s — slower than the servo's rated speed, so the
        # motor pulses stay brief and the rail holds.
        self.speed = 2
        self._last_step_time = 0

    def _write(self, angle):
        """Set the LEDC duty for `angle` — 1000..2000us out of a 20ms frame.
        Standard hobby servos treat 1ms as one end of travel and 2ms as the
        other; the old 500..2500 mapping pushed pulses beyond both ends, so
        the servos buzzed and clicked at the extremes.
        """
        pulse_us = 1000 + (angle / 180.0) * 1000
        self.pwm.duty_ns(int(pulse_us * 1000))
        self.angle = angle
        self.holding = True

    def release(self):
        """Put the servo to sleep: drop the PWM frame so it draws no hold
        current and the wheels settle to their linkage rest position. The next
        set_angle() turns the frame back on, so steering works after a release
        the same as after boot. Use it when the robot is parked and the wheels
        should stay parallel without draining the battery on hold torque."""
        self.pwm.duty(0)
        self.target = None
        self.holding = False

    def _step(self):
        """Advance one step. Kept for the main loop's 20ms tick."""
        if self.target is None or self.angle == self.target:
            return False

        diff = self.target - self.angle
        step_dir = 1 if diff > 0 else -1
        nxt = self.angle + (step_dir * self.speed)

        # Snap to target on last step
        if (step_dir > 0 and nxt >= self.target) or \
           (step_dir < 0 and nxt <= self.target):
            nxt = self.target

        # Hardware keeps the frame running, so the target needs no extra pulses.
        self._write(nxt)
        return self.angle == self.target

    def set_angle(self, angle):
        """Schedule smooth move to `angle` — returns immediately."""
        angle = max(0, min(180, int(angle)))
        # If already holding this angle, nothing to do. After a release the
        # servo is asleep, so the same angle must still wake it up.
        if self.angle == angle and self.holding:
            return
        # Waking from sleep: write the commanded pulse right away (stepping is
        # a no-op when the angle is unchanged, which would leave it asleep).
        if not self.holding:
            self._write(angle)
            self.target = None
            print("S" + str(angle))
            return
        self.target = angle
        print("S" + str(angle))

    def get_current_angle(self):
        """Return the last known position."""
        return self.angle


# The linkage connects both servos mechanically, so they are driven together.
servo = Servo(PINS["servo_left"])
servo_2 = Servo(PINS["servo_right"])

# --- MOTOR (MX1508 Dual PWM) ---


class Motor:
    def __init__(self):
        # MX1508 needs two independent PWM pins for full power control
        self.pwm_fwd = PWM(Pin(PINS["motor_in1"]))   # IN1 — forward direction
        self.pwm_rev = PWM(Pin(PINS["motor_in2"]))   # IN2 — reverse direction
        self.pwm_fwd.freq(500)       # 500Hz — smooth for motor, no skakanie
        self.pwm_rev.freq(500)

    def stop(self):
        """Stop motor completely"""
        self.pwm_fwd.duty_u16(0)
        self.pwm_rev.duty_u16(0)

    def run(self, speed):
        """Set motor speed — speed is -100 (full reverse) to 100 (full forward).

        MX1508 dual PWM: IN1 for forward, IN2 for reverse.
        At T100/T-100 both active pins get full duty (65535), inactive gets 0.
        """
        if speed == 0:
            self.stop()
            return

        abs_speed = min(abs(speed), 100)
        # Scale to 16-bit PWM range (max ~65535, use ~65500 to be safe)
        duty = int(abs_speed * 655.0)

        if speed > 0:
            # Forward — IN1=full, IN2=off
            self.pwm_fwd.duty_u16(duty)    # IN1 gets speed PWM
            self.pwm_rev.duty_u16(0)       # IN2 off
        else:
            # Reverse — IN1=off, IN2=full
            self.pwm_fwd.duty_u16(0)       # IN1 off
            self.pwm_rev.duty_u16(duty)    # IN2 gets speed PWM


motor = Motor()

# --- WEB SOCKET SERVER ---

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def ws_accept(key):
    """Sec-WebSocket-Accept for a handshake key."""
    digest = hashlib.sha1((key + WS_GUID).encode()).digest()
    return binascii.b2a_base64(digest)[:-1].decode()


def ws_send(sock, text):
    """Send one unmasked text frame."""
    data = text.encode()
    hdr = bytearray([0x81])
    n = len(data)
    if n < 126:
        hdr.append(n)
    elif n < 65536:
        hdr.append(126)
        hdr += struct.pack(">H", n)
    else:
        hdr.append(127)
        hdr += struct.pack(">Q", n)
    send_all(sock, bytes(hdr) + data)


def ws_parse(buf):
    """Parse one frame from the head of `buf`.

    Returns (opcode, payload, consumed) or None when more bytes are needed.
    Client frames are masked; the mask is applied before the payload is
    returned.
    """
    if len(buf) < 2:
        return None
    opcode = buf[0] & 0x0F
    masked = buf[1] & 0x80
    ln = buf[1] & 0x7F
    off = 2
    if ln == 126:
        if len(buf) < 4:
            return None
        ln = struct.unpack(">H", buf[2:4])[0]
        off = 4
    elif ln == 127:
        if len(buf) < 10:
            return None
        ln = struct.unpack(">Q", buf[2:10])[0]
        off = 10
    if masked:
        if len(buf) < off + 4:
            return None
        mask = buf[off:off + 4]
        off += 4
    else:
        mask = None
    if len(buf) < off + ln:
        return None
    payload = bytearray(buf[off:off + ln])
    if mask:
        for i in range(ln):
            payload[i] ^= mask[i % 4]
    return opcode, bytes(payload), off + ln


def find_page():
    """Locate the control page on the internal flash or the SD card.

    Returns (path, bytes) or (None, None) when it is in neither place, so the
    screen can say the web UI is missing instead of failing silently.
    """
    for path in PAGE_PATHS:
        try:
            with open(path, "rb") as f:
                return path, f.read()
        except Exception:
            pass
    return None, None


PAGE_PATH, PAGE_BYTES = find_page()
PAGE_OK = PAGE_PATH is not None


def decode_text(data):
    """Bytes to text without the errors keyword — MicroPython's decode takes
    no keyword arguments (its own source says 'TODO: should accept kwargs
    too'), so passing errors there raises TypeError on the device."""
    try:
        return data.decode("utf-8")
    except Exception:
        return data.decode("latin-1")


def read_page():
    if PAGE_BYTES is not None:
        return PAGE_BYTES
    return b"<html><body><h1>xTRAP</h1><p>index.html not found</p></body></html>"


def send_all(sock, data):
    """Send a whole buffer on the client socket.

    The client socket is non-blocking because the main loop polls it, and a
    non-blocking send on MicroPython raises as soon as the buffer is full —
    a 4KB page hits that on the first try, and retrying a non-blocking send
    does not drain it. Send with the socket temporarily blocking and a
    timeout, then hand it back to the poll loop. Anything that still fails
    (dead peer, timeout) propagates to the caller, which drops the client.
    """
    try:
        sock.setblocking(True)
        sock.settimeout(2.0)
        off = 0
        while off < len(data):
            sent = sock.send(data[off:])
            if sent:
                off += sent
    finally:
        try:
            sock.setblocking(False)
        except Exception:
            pass


def send_page(cli):
    body = read_page()
    head = ("HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            "Content-Length: %d\r\n"
            "Connection: close\r\n\r\n" % len(body))
    send_all(cli, head.encode() + body)


connect_wifi()

listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listen.bind(("0.0.0.0", PORT))
listen.listen(1)
listen.setblocking(False)

poll = select.poll()
poll.register(listen, select.POLLIN)

client = None
client_buf = b""
client_ws = False


def drop_client():
    global client, client_buf, client_ws
    if client is not None:
        try:
            poll.unregister(client)
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
    client = None
    client_buf = b""
    client_ws = False


last_stats = 0
gc_collect_at = 0
# When the motor was last commanded. A timestamp, not a sticky boolean —
# a boolean would latch true after the first packet and disable the failsafe.
last_drive_time = time.ticks_ms()
# Last commanded throttle. 0 = nothing to stop, so the failsafe stays quiet
# until the car is actually moving.
throttle = 0
dirty = True
last_draw = 0
# Last network error, shown on the screen: a browser that vanishes mid-send
# must not look like a silent death.
last_error = ""


def gc_collect():
    global gc_collect_at
    now = time.ticks_ms()
    if time.ticks_diff(now, gc_collect_at) > 30000:
        gc.collect()
        gc_collect_at = now


def handle_text(msg):
    """One command from the browser: S,<angle> / T,<throttle> / X."""
    global throttle, last_drive_time, dirty
    parts = msg.split(",")

    if parts[0] == "S" and len(parts) > 1:
        try:
            angle = int(parts[1])
        except ValueError:
            return
        servo.set_angle(angle)
        servo_2.set_angle(angle)
        dirty = True

    elif parts[0] == "X":
        servo.release()
        servo_2.release()
        print("X release")
        dirty = True

    elif parts[0] == "T" and len(parts) > 1:
        try:
            throttle = int(parts[1])
        except ValueError:
            return
        motor.run(throttle)
        last_drive_time = time.ticks_ms()
        print("T" + str(throttle))
        dirty = True


def draw():
    """Status screen: address, WiFi, battery, steering, throttle, link, errors."""
    DISPLAY.fill(CONFIG.palette[2])
    DISPLAY.text("xTRAP", 8, 6, CONFIG.palette[8])
    DISPLAY.text("IP " + str(nic.ifconfig()[0]), 8, 22, CONFIG.palette[8])

    rssi = wifi_rssi()
    wifi = "WIFI ?"
    if rssi is not None:
        wifi = "WIFI %d %s" % (rssi, rssi_bars(rssi))
    DISPLAY.text(wifi, 8, 38, CONFIG.palette[8])

    DISPLAY.text("BAT %d%%" % pct, 8, 54, CONFIG.palette[8])
    DISPLAY.text("STR %d" % servo.angle, 8, 70, CONFIG.palette[8])
    DISPLAY.text("THR %d" % throttle, 8, 86, CONFIG.palette[8])
    DISPLAY.text("WS " + ("link" if (client and client_ws) else "no link"), 8, 102, CONFIG.palette[8])

    warn = last_error or ("" if PAGE_OK else "WEBUI MISSING")
    hint = "ENT rel  SPC stop"
    DISPLAY.text(("ERR " + warn[:25]) if warn else hint, 8, 118, warn_color())
    DISPLAY.show()


def warn_color():
    """Red-ish palette entry, falling back to the light text color."""
    try:
        return CONFIG.palette[11]
    except Exception:
        return CONFIG.palette[8]


def _serve_client(ev):
    """Handle one poll event on the connected client.

    Split out so the main loop can wrap it: a browser that vanishes
    mid-response must drop the client, not crash the app.
    """
    global client_buf, client_ws
    if ev & (select.POLLHUP | select.POLLERR):
        drop_client()
        return
    try:
        data = client.recv(512)
    except OSError:
        # EAGAIN: the poll said readable but the data is not here yet. That is
        # "try again later", not "the client is gone" — dropping here is what
        # answered every request with an empty response.
        return
    if not data:
        drop_client()
        return
    client_buf += data

    if not client_ws:
        if b"\r\n\r\n" not in client_buf:
            return
        head, client_buf = client_buf.split(b"\r\n\r\n", 1)
        lines = decode_text(head).split("\r\n")
        request_line = lines[0] if lines else ""
        path = request_line.split(" ")[1] if " " in request_line else "/"
        key = None
        for line in lines[1:]:
            name, _, value = line.partition(":")
            if name.strip().lower() == "sec-websocket-key":
                key = value.strip()
        if path == "/ws" and key:
            resp = ("HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    "Sec-WebSocket-Accept: %s\r\n\r\n" % ws_accept(key))
            send_all(client, resp.encode())
            client_ws = True
            print("WebSocket up")
        else:
            send_page(client)
            drop_client()
        return

    while True:
        frame = ws_parse(client_buf)
        if frame is None:
            break
        opcode, payload, used = frame
        client_buf = client_buf[used:]
        if opcode == 0x8:
            drop_client()
            break
        elif opcode == 0x9:
            send_all(client, bytes([0x8A, len(payload)]) + payload)
        elif opcode == 0x1:
            handle_text(decode_text(payload).strip())


print("Web control on http://%s/ (ws /ws)" % nic.ifconfig()[0])
if PAGE_OK:
    print("Web UI:", PAGE_PATH, len(PAGE_BYTES), "bytes")
else:
    print("WEBUI MISSING: no index.html in", PAGE_PATHS)

while True:
    now = time.ticks_ms()

    # --- KEYS ---
    for key in INPUT.get_new_keys():
        if key == "ENT":
            servo.release()
            servo_2.release()
            print("X release")
            dirty = True
        elif key == "SPC":
            throttle = 0
            motor.stop()
            last_drive_time = now
            dirty = True
        elif key == "ESC":
            servo.set_angle(90)
            servo_2.set_angle(90)
            dirty = True

    # --- SERVO STEP (throttled to ~50Hz) ---
    # Both step together — one mechanism, so they must not drift apart.
    if time.ticks_diff(now, servo._last_step_time) >= 20:
        servo._step()
        servo_2._step()
        servo._last_step_time = now
        servo_2._last_step_time = now

    gc_collect()

    # --- FAILSAFE ---
    # Only when the car is actually moving. stop() runs on every tick past the
    # threshold, not only the first: a T0 may never arrive, and the motor has
    # to stay off regardless. Refreshing the timestamp just rate-limits the
    # message.
    if throttle != 0 and time.ticks_diff(now, last_drive_time) > FAILSAFE_MS:
        motor.stop()
        throttle = 0
        last_drive_time = now
        dirty = True
        print("FAILSAFE: no drive command for", FAILSAFE_MS, "ms — motor stopped")

    # --- HTTP / WEBSOCKET ---
    for sock, ev in poll.poll(20):
        if sock is listen:
            try:
                conn, addr = listen.accept()
            except Exception:
                continue
            drop_client()
            conn.setblocking(False)
            poll.register(conn, select.POLLIN)
            client = conn
            client_buf = b""
            client_ws = False
            print("Client:", addr)
            dirty = True
            continue

        if sock is not client:
            continue
        try:
            _serve_client(ev)
        except Exception as exc:
            # A browser that vanishes mid-response must not take the app down;
            # MicroHydra catches an uncaught exception by dropping to the launcher.
            last_error = str(exc)
            print("client error:", last_error)
            drop_client()
            dirty = True

    # --- TELEMETRY ---
    if client is not None and client_ws and time.ticks_diff(now, last_stats) > STATS_MS:
        pct = batt.read_pct()
        try:
            ws_send(client, "B,%d" % pct)
        except Exception:
            drop_client()
            continue
        last_stats = now
        dirty = True

    # --- SCREEN ---
    if dirty or time.ticks_diff(now, last_draw) > 250:
        draw()
        last_draw = now
        dirty = False

    time.sleep(0.02)
