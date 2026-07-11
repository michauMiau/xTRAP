# network.py — centralized networking for RC control
import socket
import math
import threading
from state import state
from discovery import DISCOVERY_PORT, probe_device

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
_car_addr = ("192.168.1.225", 5005)  # Default; can be overridden by discovery or manual input
_car_addr_lock = threading.Lock()

PORT_RECV = 5005


def get_car_addr():
    """Thread-safe getter for CAR_ADDR."""
    with _car_addr_lock:
        return tuple(_car_addr)


def set_car_addr(addr):
    """Thread-safe setter for CAR_ADDR. Accepts (ip, port) or (host, port)."""
    if isinstance(addr, str):
        addr = (addr, 5005)
    with _car_addr_lock:
        _car_addr[0] = addr[0]
        if len(addr) > 1:
            _car_addr[1] = addr[1]


def network_loop():
    """Start the network receive loop in a background thread."""

    def recv_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
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
                            with state._lock:
                                state.ax = ax
                                state.ay = ay
                                state.az = az

                                az_corrected = az - 9.81
                                g = math.sqrt(ax*ax + ay*ay + az_corrected*az_corrected) / 9.81
                                state.g = g
                                state.max_g = max(state.max_g, g)

                        elif msg[0] == "B":
                            if len(msg) > 1:
                                with state._lock:
                                    state.batt_pct = float(msg[1])

                    except Exception:
                        pass
        finally:
            sock.close()

    import threading
    threading.Thread(target=recv_loop, daemon=True).start()


def send_steering(angle):
    """Send steering command to Cardputer."""
    try:
        msg = f"S,{int(angle)}"
        addr = get_car_addr()
        send_sock.sendto(msg.encode(), addr)
        print("sent" + msg)
    except Exception as e:
        print(f"[network] send_steering failed: {e}")


def send_throttle(throttle):
    """Send throttle command to Cardputer."""
    try:
        msg = f"T,{int(throttle)}"
        addr = get_car_addr()
        send_sock.sendto(msg.encode(), addr)
        print("throttle sent: " + msg)
    except Exception as e:
        print(f"[network] send_throttle failed: {e}")
