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

# --- SERVO ---
class Servo:
    def __init__(self, pin):
        self.pin = Pin(pin, Pin.OUT)
        self.angle = 90 # Set 90 as default

    def write_pulse(self, us):
        self.pin.on()
        time.sleep_us(us)
        self.pin.off()

    def set_angle(self, angle):
        angle = max(0, min(180, angle))
        self.angle = angle
        print("S" + str(angle))
        pulse = int(500 + (angle / 180) * 2000)
        for _ in range(3):
            self.write_pulse(pulse)
            time.sleep_ms(20)
servo = Servo(3)  # your servo pin

# --- MOTOR (H-Bridge PWM) ---
# H-bridge direction pins — one per side of the tracked robot
DIR_LEFT = Pin(4, Pin.OUT)  # left motor direction
DIR_RIGHT = Pin(6, Pin.OUT)  # right motor direction
class Motor:
    def __init__(self):
        self.speed = PWM(DIR_LEFT)  # PWM speed pin (left side of H-bridge input)
        self.speed.freq(50)          # Low freq for H-bridge PWM signal
        self.speed.duty_u16(0)       # Start stopped
        self._last_dir = None

    def run(self, speed):
        """Set motor speed — speed is -100 (full reverse) to 100 (full forward).
        
        Adds dead-time between direction changes to prevent H-bridge shoot-through.
        MX1508 needs both outputs off briefly when switching direction.
        """
        if speed < 0:
            new_dir = "REV"
        elif speed > 0:
            new_dir = "FWD"
        else:
            # Coast — kill everything first, then set dir if needed next time
            self.speed.duty_u16(0)
            DIR_LEFT.value(False)
            DIR_RIGHT.value(False)
            self._last_dir = None
            return
        
        # Dead-time: turn off PWM before switching direction pins
        was_rev = (self._last_dir == "REV")
        is_now_rev = (new_dir == "REV")
        
        if was_rev != is_now_rev or speed > 0 and self._last_dir is None:
            # Need to switch direction — turn off PWM first for dead time
            self.speed.duty_u16(0)
            time.sleep_us(500)  # ~500µs dead time
            
            DIR_LEFT.value(False)
            DIR_RIGHT.value(False)
            
            if new_dir == "REV":
                DIR_LEFT.value(True)
                DIR_RIGHT.value(False)
            else:
                DIR_LEFT.value(False)
                DIR_RIGHT.value(True)
        
        self._last_dir = new_dir
        
        # Now set PWM speed (safe — direction is already stable)
        abs_speed = abs(speed)
        if abs_speed > 100:
            abs_speed = 100
        self.speed.duty_u16(int(abs_speed * 327.68))

motor = Motor()
last_throttle_time = time.ticks_ms()

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

COAST_TIMEOUT_MS = 2000  # Auto-coast after 2s without throttle command (WiFi UDP latency)


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

        if parts[0] == "T" and len(parts) > 1:
            throttle = int(parts[1])
            motor.run(throttle)
            last_throttle_time = now
            print("T" + str(throttle))
    except Exception:
        pass

    # Auto-coast if no throttle command received within timeout
    if time.ticks_diff(now, last_throttle_time) < COAST_TIMEOUT_MS:
        pass  # Keep current state
    else:
        motor.run(0)  # Coast — kill everything

    # --- SLOW ---
    if time.ticks_diff(now, last_stats_time) > 5000: # Lowered the time to 5s
        msg = f"B,{pct},0"
        sock.sendto(msg.encode(), (HOST_IP, PORT))

        last_stats_time = now

    time.sleep(0.02)
