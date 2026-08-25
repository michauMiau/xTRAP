# network.py — centralized networking for RC control
import socket
import math
import logging
import threading
from state import state
import settings

log = logging.getLogger(__name__)

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
send_sock.settimeout(5.0)  # Prevent blocking on offline car

_car_addr_list = [settings.get_car_ip(), 5005]  # mutable list for thread-safe updates
_car_addr_lock = threading.Lock()

PORT_RECV = 5005

_recv_stop_event = threading.Event()


def get_car_addr():
    """Thread-safe getter for CAR_ADDR."""
    with _car_addr_lock:
        return (_car_addr_list[0], _car_addr_list[1])


def set_car_addr(addr):
    """Thread-safe setter for CAR_ADDR. Accepts (ip, port) or just an ip string."""
    if isinstance(addr, str):
        addr = (addr, 5005)
    with _car_addr_lock:
        settings.set_car_ip(addr[0])
        _car_addr_list[0] = addr[0]
        if len(addr) > 1:
            _car_addr_list[1] = addr[1]


def network_loop():
    """Start the network receive loop in a background thread."""

    def recv_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("0.0.0.0", PORT_RECV))
            sock.settimeout(0.1)  # Non-blocking with timeout for CPU safety

            while not _recv_stop_event.is_set():
                latest = None  # Reset each iteration — prevents stale replay
                try:
                    data, _ = sock.recvfrom(1024)
                    latest = data
                except socket.timeout:
                    pass  # Timeout is normal with settimeout — keep draining
                except Exception as e:
                    log.warning(f"[recv_loop] recv error: {e}")
                    continue

                if latest:
                    try:
                        msg = latest.decode().split(",")

                        if msg[0] == "M":
                            # Validate we have at least 3 values for IMU data
                            if len(msg) < 4:
                                log.debug(f"[recv_loop] M message incomplete: {len(msg)} fields")
                                continue
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
                                try:
                                    pct = float(msg[1])
                                    if 0 <= pct <= 100:
                                        with state._lock:
                                            state.batt_pct = pct
                                except ValueError:
                                    pass

                    except Exception as e:
                        log.debug(f"[recv_loop] parse error: {e}")

        finally:
            try:
                sock.close()
            except Exception:
                pass

    threading.Thread(target=recv_loop, daemon=True).start()


def stop_network():
    """Signal recv_loop to stop (graceful shutdown)."""
    _recv_stop_event.set()


def send_steering(angle):
    """Send steering command to Cardputer."""
    try:
        msg = f"S,{int(angle)}"
        addr = get_car_addr()
        send_sock.sendto(msg.encode(), addr)
    except Exception as e:
        log.error(f"[network] send_steering failed: {e}")


def send_throttle(throttle):
    """Send throttle command to Cardputer."""
    try:
        msg = f"T,{int(throttle)}"
        addr = get_car_addr()
        send_sock.sendto(msg.encode(), addr)
    except Exception as e:
        log.error(f"[network] send_throttle failed: {e}")
