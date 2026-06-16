from machine import Pin
import time

in1 = Pin(6, Pin.OUT)   # change pins if needed
in2 = Pin(4, Pin.OUT)

def forward():
    in1.value(1)
    in2.value(0)

def reverse():
    in1.value(0)
    in2.value(1)

def stop():
    in1.value(0)
    in2.value(0)

while True:
    print("forward")
    forward()
    time.sleep(2)

    print("stop")
    stop()
    time.sleep(1)

    print("reverse")
    reverse()
    time.sleep(2)

    print("stop")
    stop()
    time.sleep(2)