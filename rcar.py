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

# --- MOTOR (MX1508 Dual PWM) ---
class Motor:
    def __init__(self):
        self.pwm_fwd = PWM(Pin(4))   # IN1 — forward
        self.pwm_rev = PWM(Pin(6))   # IN2 — reverse
        self.pwm_fwd.freq(20000)     # 20kHz for smooth motor control
        self.pwm_rev.freq(20000)

    def stop(self):
        """Stop motor completely"""
        self.pwm_fwd.duty_u16(0)
        self.pwm_rev.duty_u16(0)

    def run(self, speed):
        """Set motor speed — speed is -100 (full reverse) to 100 (full forward).
        
        MX1508 dual PWM control:
        - Forward: IN1=ON, IN2=OFF
        - Reverse: IN1=OFF, IN2=ON  
        - Stop: both OFF
        """
        if speed == 0:
            self.stop()
            return
        
        # Normalize speed to 0-100 range
        abs_speed = min(abs(speed), 100)
        
        if speed > 0:
            # Forward — IN1 ON, IN2 OFF
            self.pwm_fwd.duty_u16(int(abs_speed * 327.68))  # 0-100% → 0-32768 (16-bit)
            self.pwm_rev.duty_u16(0)
        else:
            # Reverse — IN1 OFF, IN2 ON
            self.pwm_fwd.duty_u16(0)
            self.pwm_rev.duty_u16(int(abs_speed * 327.68))

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
