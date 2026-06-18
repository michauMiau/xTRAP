# network.py — centralized networking for RC control
import logging
import socket
import threading
import math
from state import state

log = logging.getLogger(__name__)

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
CAR_ADDR = ("192.168.1.174", 5006)

PORT_RECV = 5005  # Port for receiving sensor data from Cardputer

# Track whether network thread is running (for lifecycle management)
_network_thread_active = False


def connect(addr=None):
    """Connect to the robot — sets CAR_ADDR and starts the receive loop if not already running.
    
    Args:
        addr: Optional IP:port tuple. Defaults to CAR_ADDR.
    """
    global _network_thread_active, send_sock
    
    if addr is None:
        # Use default from config (user can override via UI)
        pass  # CAR_ADDR already set
    
    try:
        send_sock.sendto(b"PING", CAR_ADDR)
        log.info(f"Connected to {CAR_ADDR}")
    except Exception as e:
        log.error(f"Failed to connect to {CAR_ADDR}: {e}")

def disconnect():
    """Disconnect from the robot — stop network thread and close sockets."""
    global _network_thread_active, send_sock
    
    # Close send socket
    try:
        if send_sock:
            send_sock.close()
    except Exception as e:
        log.error(f"Error closing send socket: {e}")

def is_connected():
    """Check if network thread is running."""
    return _network_thread_active


def _start_network_loop():
    """Start the network receive loop in a background thread. Called from App.on_start()."""
    global _network_thread_active
    
    def loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("0.0.0.0", PORT_RECV))
            sock.setblocking(False)
        except Exception as e:
            log.error(f"Failed to bind receive port {PORT_RECV}: {e}")
            return
        
        _network_thread_active = True
        latest = None
        
        while _network_thread_active:
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

                except Exception as e:
                    log.error(f"Error processing network message: {e}")

    threading.Thread(target=loop, daemon=True).start()


def _stop_network_loop():
    """Stop the network receive loop. Called from App.on_stop()."""
    global _network_thread_active
    
    # Close send socket when stopping
    try:
        if send_sock:
            send_sock.close()
    except Exception as e:
        log.error(f"Error closing send socket on stop: {e}")

def network_loop():
    """Legacy entry point — kept for backward compatibility. Use _start_network_loop instead."""
    _start_network_loop()


            
def send_steering(angle):
    """Send steering command to Cardputer."""
    try:
        msg = f"S,{int(angle)}"
        send_sock.sendto(msg.encode(), CAR_ADDR)
        log.debug(f"sent {msg}")
    except Exception as e:
        log.error(f"Error sending steering command '{msg}': {e}")

def send_throttle(throttle):
    """Send throttle command to Cardputer."""
    try:
        msg = f"T,{int(throttle)}"
        send_sock.sendto(msg.encode(), CAR_ADDR)  # Unsure if both send msg will cause race condidtions?
        log.debug(f"sent {msg}")
    except Exception as e:
        log.error(f"Error sending throttle command '{msg}': {e}")
