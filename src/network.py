# network.py — centralized networking for RC control
import socket
import math
from state import state
from discovery import DISCOVERY_PORT, probe_device

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
CAR_ADDR = ("192.168.1.225", 5005)  # Default; can be overridden by discovery or manual input

PORT_RECV = 5005


def network_loop():
    """Start the network receive loop in a background thread."""

    def recv_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", PORT_RECV))
        sock.setblocking(False)

        latest = None

        while True:
            try:
                while True:  # drain buffer
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

    import threading
    threading.Thread(target=recv_loop, daemon=True).start()


def send_steering(angle):
    """Send steering command to Cardputer."""
    msg = f"S,{int(angle)}"
    send_sock.sendto(msg.encode(), CAR_ADDR)
    print("sent" + msg)


def send_throttle(throttle):
    """Send throttle command to Cardputer."""
    msg = f"T,{int(throttle)}"
    send_sock.sendto(msg.encode(), CAR_ADDR)
    print("throttle sent: " + msg)
