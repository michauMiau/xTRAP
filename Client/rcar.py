# "host.py" file, minify, compile into .mpy for production or something?
import time
import socket
import network
from lib.hydra.config import Config
from lib.userinput import bmi270
from lib.battlevel import Battery
from machine import I2C, ADC, Pin, PWM
# This code is NOT ISO 270001 Compliant

batt = Battery()
pct = batt.read_pct() # The battery percent var to send

# --- WIFI ---
nic = network.WLAN(network.STA_IF)
config = Config()
nic.config(pm=0) # Tried to disable power managment on the wifi chip

# --- UDP ---
HOST_IP = "192.168.1.8"  # TODO: your PC IP
PORT = 5005

def connect_wifi():
    if not nic.active():
        nic.active(True)

    if not nic.isconnected():
        while True:
            try:
                nic.connect(config['wifi_ssid'], config['wifi_pass'])
                break
            except:
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
    except:
        return 0.0, 0.0, 0.0

# CONFIGURING THE SCREEN BACKLIGHT PWM SO IT DOESN'T GO CRAZY
BACKLIGHT_PIN = 38  # Skip this whole section if you don't have a cardputer/backlight
backlight = PWM(Pin(BACKLIGHT_PIN))
backlight.freq(1000)     # idk what chatgpt was cooking here
backlight.duty(0)        # SCREEN OFF

# --- SERVO ---
class Servo:
    def __init__(self, pin):
        self.pin = Pin(pin, Pin.OUT)
        self.angle = 90

    def write_pulse(self, us):
        self.pin.on()
        time.sleep_us(us)
        self.pin.off()

    def set_angle(self, angle):
        angle = max(0, min(180, angle))
        self.angle = angle
        print("SET angle" + angle)
        pulse = int(500 + (angle / 180) * 2000)

        for _ in range(3):
            self.write_pulse(pulse)
            time.sleep_ms(20)

servo = Servo(4)  # your servo pin

# Setup connections
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
sock.setblocking(False)

# --- MAIN LOOP ---
connect_wifi()

last_stats_time = 0

while True:
    now = time.ticks_ms()

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

    except:
        pass

    # --- SLOW ---
    if time.ticks_diff(now, last_stats_time) > 5000: # Lowered the time to 5s
        msg = f"B,{pct},0"
        sock.sendto(msg.encode(), (HOST_IP, PORT))

        last_stats_time = now

    time.sleep(0.02)
