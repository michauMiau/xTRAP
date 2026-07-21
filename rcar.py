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
BACKLIGHT_PIN = 38  # Skip this whole section if you don't have a cardputer/backlight
backlight = PWM(Pin(BACKLIGHT_PIN))
backlight.freq(1000)     # set freq to reasonable amount
backlight.duty(0)        # Backlight off

# --- SERVO (smooth movement to reduce current spike) ---

class Servo:
    """Smooth-stepping servo — moves toward target at `speed` deg/step,
    not jumping instantly. Reduces peak current draw vs direct pulse."""

    def __init__(self, pin, speed=5):
        """
        pin   – GPIO number (int)
        speed – degrees per step; lower = slower, gentler on power supply.
                Default 5: full sweep (~90 deg) takes ~180 ms at 20 ms/step.
        """
        self.pin = Pin(pin, Pin.OUT)
        self.speed = speed
        self.angle = 90

    def write_pulse(self, us):
        """Send a single servo pulse of `us` microseconds."""
        self.pin.on()
        time.sleep_us(us)
        self.pin.off()

    @staticmethod
    def angle_to_us(angle: int) -> int:
        """Map 0-180 degrees to 500-2500 microseconds pulse width."""
        return int(500 + (angle / 180.0) * 2000)

    def get_current_angle(self) -> int:
        """Return the last known angle from this instance."""
        return self.angle

    def set_angle(self, angle, speed=None):
        """Move smoothly to `angle`. Returns immediately when already there."""
        angle = max(0, min(180, int(angle)))
        speed = self.speed if speed is None else int(speed)
        current = self.get_current_angle()

        if current == angle:
            return  # nothing to do

        step = speed if (angle - current) > 0 else -speed
        while True:
            next_angle = current + step
            if (step > 0 and next_angle >= angle) or (step < 0 and next_angle <= angle):
                next_angle = angle  # snap to target on last step

            pulse = Servo.angle_to_us(next_angle)
            # 3 pulses per position (standard hobby-servo settling)
            for _ in range(3):
                self.write_pulse(pulse)
                time.sleep_ms(20)

            self.angle = next_angle
            current = next_angle

            if current == angle:
                break

        print("S" + str(angle))
servo = Servo(2, speed=5)

# --- MOTOR (MX1508 Dual PWM) ---
class Motor:
    def __init__(self):
        # MX1508 needs two independent PWM pins for full power control
        self.pwm_fwd = PWM(Pin(6))   # IN1 — forward direction
        self.pwm_rev = PWM(Pin(4))   # IN2 — reverse direction
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


def gc_collect():
    global gc_collect_at
    now = time.ticks_ms()
    if time.ticks_diff(now, gc_collect_at) > 30000:
        gc.collect()
        gc_collect_at = now


while True:
    now = time.ticks_ms()
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

        if parts[0] == "S" and len(parts) > 1:
            angle = int(parts[1])
            servo.set_angle(angle)

        # T command: set throttle once, hold state until next T packet (T0 stops motor)
        if parts[0] == "T" and len(parts) > 1:
            throttle = int(parts[1])
            motor.run(throttle)
            print("T" + str(throttle))
    except Exception:
        pass

    # --- SLOW ---
    if time.ticks_diff(now, last_stats_time) > 5000: # Lowered the time to 5s
        msg = f"B,{pct},0"
        sock.sendto(msg.encode(), (HOST_IP, PORT))

        last_stats_time = now

    time.sleep(0.02)
