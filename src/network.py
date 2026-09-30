# network.py — centralized networking for RC control
import socket
import math
import logging
import threading
from kivy.clock import Clock
from state import state
import settings

log = logging.getLogger(__name__)

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
send_sock.settimeout(5.0)  # Prevent blocking on offline car

_car_addr_list = [settings.get_car_ip(), 5005]  # mutable list for thread-safe updates
_car_addr_lock = threading.Lock()

PORT_RECV = 5005

# How often a held throttle is repeated. The firmware's failsafe threshold is
# 1000ms, so this must stay well under it while costing almost nothing.
KEEPALIVE_S = 0.25

_recv_stop_event = threading.Event()

# A steering/throttle command has a physical meaning only while the button is
# held, so it is sent once on press. The firmware's failsafe would then fire
# mid-hold, so the client repeats the current throttle on a slow timer — the
# command is idempotent, and 4Hz is far below the firmware's 50Hz tick.
_held_throttle = 0
_keepalive_id = None


def announce_car_addr():
    """Tell the car our IP, so it can send telemetry back to us.

    The car has our address hardcoded, which breaks the moment the PC's IP
    changes. Sending it in every packet would be simpler, but the firmware
    binds one socket for both directions. So: a one-line handshake the car
    latches, plus a repeat while idle so a firmware that booted after the
    client still learns it.
    """
    addr = get_car_addr()
    msg = f"H,{addr[0]}"
    try:
        send_sock.sendto(msg.encode(), addr)
    except Exception as e:
        log.debug(f"[announce] failed: {e}")


def set_held_throttle(level):
    """Hold the throttle down: remember it and keep repeating it.

    The firmware treats 1000ms without a T packet as a lost link and stops the
    motor, so a single press is not enough — the command has to keep coming
    while the button is down and stop the moment it is released.
    """
    global _held_throttle, _keepalive_id  # pylint: disable=global-statement
    _held_throttle = level

    if not level:
        if _keepalive_id is not None:
            _keepalive_id.cancel()
            _keepalive_id = None
        send_throttle(0)
        return

    send_throttle(level)
    if _keepalive_id is None:
        _keepalive_id = Clock.schedule_interval(
            lambda _dt: send_throttle(_held_throttle), KEEPALIVE_S
        )


def clear_held_throttle():
    """Drop any held throttle — used on pause, so the car does not keep driving."""
    set_held_throttle(0)


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
