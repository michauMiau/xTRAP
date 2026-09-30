""" The car micropthon code, compile into .mpy for production or something? """
from lib.hydra.config import Config
from lib.userinput import bmi270
from lib.battlevel import Battery
from machine import I2C, Pin, PWM
import socket
import network
import time
import gc
# This code is NOT ISO 270001 Compliant

batt = Battery()
pct = batt.read_pct() # The battery percent var to send

# --- PINS ---
# Every output in one place, so a rewiring is a diff here and not a hunt
# through the driver classes.
#
# I2C(0) is GPIO8/9 on this firmware, per MicroHydra's mpconfigboard.h. Do not
# infer bus pins from a bus number: the stock Cardputer firmware maps I2C(0)
# to GPIO1/2, which would collide with servo_left.
#
# bench-verified: motor_in1, motor_in2, servo_left
# never driven before: servo_right
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

# --- WIFI ---
nic = network.WLAN(network.STA_IF)
config = Config()
nic.config(pm=0) # Tried to disable power managment on the wifi chip

# --- UDP ---
HOST_IP = "192.168.1.235"  # TODO: maybe implement some kind of system to automatically get computer ip?
PORT = 5005

def connect_wifi():
    if not nic.active():
        nic.active(True)

    if not nic.isconnected():
        while True:
            try:
                nic.connect(config['wifi_ssid'], config['wifi_pass'])
                break
            except Exception:
                time.sleep_ms(500)

        while not nic.isconnected():
            time.sleep_ms(500)

    print("Connected:", nic.ifconfig())


# --- IMU Setup  ---
i2c = I2C(0)
imu = bmi270.BMI270(i2c)
def read_accel():
    try:
        ax, ay, az = imu.acceleration
        return ax, ay, az
    except Exception:
        return 0.0, 0.0, 0.0


# CONFIGURING THE SCREEN BACKLIGHT PWM SO IT DOESN'T GO CRAZY
BACKLIGHT_PIN = PINS["backlight"]  # Skip this whole section if you don't have a cardputer/backlight
backlight = PWM(Pin(BACKLIGHT_PIN))
backlight.freq(1000)     # set freq to reasonable amount
backlight.duty(0)        # Backlight off

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
        self.speed = 5
        self._last_step_time = 0

    def _write(self, angle):
        """Set the LEDC duty for `angle` — 500..2500us out of a 20ms frame."""
        pulse_us = 500 + (angle / 180.0) * 2000
        self.pwm.duty_ns(int(pulse_us * 1000))
        self.angle = angle

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
        if self.angle == angle:
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

# Setup connections
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
sock.setblocking(False)

# --- MAIN LOOP ---
connect_wifi()

last_stats_time = 0
gc_collect_at = 0
# When the motor was last commanded. A timestamp, not a sticky boolean —
# a boolean would latch true after the first packet and disable the failsafe.
last_drive_time = time.ticks_ms()
# Last commanded throttle. 0 = nothing to stop, so the failsafe stays quiet
# until the car is actually moving.
throttle = 0


def gc_collect():
    global gc_collect_at
    now = time.ticks_ms()
    if time.ticks_diff(now, gc_collect_at) > 30000:
        gc.collect()
        gc_collect_at = now


while True:
    now = time.ticks_ms()

    # --- SERVO STEP (throttled to ~50Hz) ---
    # Both step together — one mechanism, so they must not drift apart.
    if time.ticks_diff(now, servo._last_step_time) >= 20:
        done = servo._step()
        servo_2._step()
        servo._last_step_time = now
        servo_2._last_step_time = now

    gc_collect()

    # --- FAST ---
#    ax, ay, az = read_accel() # Disabled Sending the IMU data to prevent feature creep
#    msg = f"M,{ax},{ay},{az}"
#    sock.sendto(msg.encode(), (HOST_IP, PORT))

# --- RECEIVE CONTROL ---
    try:
        data, addr = sock.recvfrom(64)
        msg = data.decode().strip()

        parts = msg.split(",")

        # Written through globals() because a bare assignment inside this loop
        # would create a loop-local and never reach sock.sendto below.
        host = globals()

        # Client address handshake. The client announces its IP so the car can
        # send telemetry back without a hardcoded address; anything valid is
        # latched, so a changed DHCP lease self-heals on the next announce.
        if parts[0] == "H" and len(parts) > 1:
            octets = parts[1].split(".")
            if len(octets) == 4 and all(o.isdigit() and int(o) < 256 for o in octets):
                host["HOST_IP"] = parts[1]
                print("Host:", parts[1])

        if parts[0] == "S" and len(parts) > 1:
            angle = int(parts[1])
            servo.set_angle(angle)
            servo_2.set_angle(angle)

        # T command: set throttle once, hold state until next T packet (T0 stops motor)
        if parts[0] == "T" and len(parts) > 1:
            throttle = int(parts[1])
            motor.run(throttle)
            last_drive_time = now
            print("T" + str(throttle))
    except Exception:
        pass

    # --- FAILSAFE ---
    # Only when the car is actually moving. stop() runs on every tick past the
    # threshold, not only the first: a T0 may never arrive, and the motor has
    # to stay off regardless. Refreshing the timestamp just rate-limits the
    # message.
    if throttle != 0 and time.ticks_diff(now, last_drive_time) > FAILSAFE_MS:
        motor.stop()
        throttle = 0
        last_drive_time = now
        print("FAILSAFE: no drive command for", FAILSAFE_MS, "ms — motor stopped")

    # --- SLOW ---
    if time.ticks_diff(now, last_stats_time) > 5000: # Lowered the time to 5s
        msg = f"B,{pct},0"
        sock.sendto(msg.encode(), (HOST_IP, PORT))

        last_stats_time = now

    time.sleep(0.02)
