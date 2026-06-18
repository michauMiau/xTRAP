# network.py
# Code for the networking
import socket
import math
from state import state

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
CAR_ADDR = ("192.168.1.174", 5006)  # Default — can be changed via UI connect logic

PORT_RECV = 5005  # Port for receiving sensor data from Cardputer

            
def network_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT_RECV))
    sock.setblocking(False)

    latest = None

    while True:
        try:
            while True:  # 🔥 drain buffer
                data, _ = sock.recvfrom(1024)
                latest = data
        except Exception:
            pass

        if latest:
            try:
                msg = latest.decode().split(",")

                if msg[0] == "M":
                    ax, ay, az = map(float, msg[1:])
                    state.ax = ax
                    state.ay = ay
                    state.az = az
                    
                    az = az - 9.81
                    g = math.sqrt(ax*ax + ay*ay + az*az) / 9.81
                    state.g = g
                    state.max_g = max(state.max_g, g)

                elif msg[0] == "B":
                    if len(msg) > 1:
                        state.batt_pct = float(msg[1])

            except Exception:
                pass
            
def send_steering(angle):
    msg = f"S,{int(angle)}"
    send_sock.sendto(msg.encode(), CAR_ADDR)
    print("sent" + msg)

def send_throttle(throttle): #  TODO: Send the throttle, currently unimplemented on robot side and input
    msg = f"T,{int(throttle)}"
    send_sock.sendto(msg.encode(), CAR_ADDR) # Unsure if both send msg will cause race condidtions?
