"""Device discovery via UDP multicast (239.255.0.1:5006).

Both Cardputer and Kivy app broadcast their presence periodically.
This eliminates hardcoded IPs from the codebase.

Protocol: JSON {"type": "xtrap-discovery", "ip": "...", "port": ...}
"""

import socket
import json
import threading
from kivy.clock import Clock


MULTICAST_GROUP = "239.255.0.1"
DISCOVERY_PORT = 5006
BROADCAST_INTERVAL = 3.0  # seconds between broadcasts


def get_local_ip():
    """Get device's local IP on active network interface."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 53))  # Google DNS — no real route needed
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            if addrs and not addrs[0].get("addr", "").startswith("127."):
                return addrs[0]["addr"]
        return "unknown"


def broadcast_device(ip, port):
    """Send multicast discovery packet."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    message = json.dumps({
        "type": "xtrap-discovery",
        "ip": ip,
        "port": port,
    }).encode("utf-8")

    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(get_local_ip())
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.sendto(message, (MULTICAST_GROUP, DISCOVERY_PORT))
    except OSError:
        pass  # multicast not available — fine
    finally:
        sock.close()


def start_discovery_listener(callback):
    """Start listening for discovery packets in a background thread.

    callback(ip, port) is called when a device responds.
    Returns the thread so it can be stopped if needed.
    """
    def _recv_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind(("", DISCOVERY_PORT))
            mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(get_local_ip())
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError as e:
            print(f"[discovery] bind failed: {e}")
            return

        while True:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                if (msg.get("type") == "xtrap-discovery"
                        and isinstance(msg.get("ip"), str)
                        and isinstance(msg.get("port"), int)):
                    Clock.schedule_once(
                        lambda dt, m=msg: callback(m["ip"], m["port"]), 0
                    )
            except (json.JSONDecodeError, KeyError):
                pass

        sock.close()

    thread = threading.Thread(target=_recv_loop, daemon=True)
    thread.start()
    return thread


def start_broadcasting(interval=BROADCAST_INTERVAL):
    """Periodically broadcast our presence. Returns the timer function."""
    import time as time_mod

    def _broadcast():
        while True:
            try:
                ip = get_local_ip()
                if ip != "unknown":
                    broadcast_device(ip, DISCOVERY_PORT)
            except Exception:
                pass
            time_mod.sleep(interval)

    thread = threading.Thread(target=_broadcast, daemon=True)
    thread.start()


def probe_device(host, port=DISCOVERY_PORT):
    """Send PING to host and wait for PONG. Returns (ip, port) if device responds."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)

    try:
        sock.sendto(b"PING", (host, port))
        data, addr = sock.recvfrom(1024)
        if data == b"PONG":
            return addr[0], addr[1]
    except OSError:
        pass
    finally:
        sock.close()

    return None, None


def send_pong_response():
    """Send PONG response to incoming PING (called from Cardputer side)."""
    # This would be integrated into the Cardputer's UDP listener loop
    pass  # Implemented in rcar.py on the device side
