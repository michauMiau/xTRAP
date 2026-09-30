"""Tests for the client side of the throttle keepalive and the address handshake.

network.py opens real UDP sockets and touches kivy.config, so both are stubbed.
The assertions are about what gets sent and when — the parts the firmware
depends on.
"""

import sys
import types
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))


class FakeSocket:
    """Records datagrams instead of sending them."""

    def __init__(self):
        self.sent = []
        self.timeout = None
        self.bound = None

    def settimeout(self, t):
        self.timeout = t

    def sendto(self, data, addr):
        self.sent.append((data.decode(), addr))

    def bind(self, addr):
        self.bound = addr

    def close(self):
        pass


class FakeClock:
    """Kivy Clock stand-in that lets the test fire a scheduled callback."""

    def __init__(self):
        self.intervals = {}
        self._next = 0

    def schedule_interval(self, cb, interval):
        self._next += 1
        event = types.SimpleNamespace(
            cancel=lambda: self.intervals.pop(self._next, None)
        )
        self.intervals[self._next] = (cb, interval)
        self._last_id = self._next
        return event

    def tick(self):
        """Fire every scheduled interval once."""
        for cb, _ in list(self.intervals.values()):
            cb(0.05)


@pytest.fixture
def net(monkeypatch):
    """network.py with fakes for the socket, the clock and the config store."""
    import network

    fake_sock = FakeSocket()
    monkeypatch.setattr(network, "send_sock", fake_sock)
    monkeypatch.setattr(network, "_car_addr_list", ["192.168.1.200", 5005])
    network._held_throttle = 0
    network._keepalive_id = None
    network.send_sock = fake_sock

    fake_clock = FakeClock()
    monkeypatch.setattr(network, "Clock", fake_clock)
    return network, fake_sock, fake_clock


def test_held_throttle_sends_immediately(net):
    """Press must reach the car now, not on the next tick."""
    network, sock, _ = net
    network.set_held_throttle(100)
    assert sock.sent[0][0] == "T,100"


def test_held_throttle_repeats_while_held(net):
    """The firmware's failsafe is 1000ms, so a single press is not enough."""
    network, sock, clock = net
    network.set_held_throttle(100)
    before = len(sock.sent)

    clock.tick()
    clock.tick()

    repeats = [m for m, _ in sock.sent[before:]]
    assert repeats == ["T,100", "T,100"]


def test_keepalive_interval_is_well_under_the_failsafe(net):
    """250ms leaves 4x margin against the firmware's 1000ms threshold."""
    network, _, clock = net
    network.set_held_throttle(100)
    _, interval = list(clock.intervals.values())[0]
    assert interval < 0.5
    assert interval > 0


def test_release_stops_the_repeating_and_sends_zero(net):
    """The car must stop the moment the button comes up."""
    network, sock, clock = net
    network.set_held_throttle(100)
    before = len(sock.sent)

    network.set_held_throttle(0)

    assert sock.sent[-1][0] == "T,0"
    assert not clock.intervals, "the timer is still running after release"
    assert len(sock.sent) == before + 1, "release sent more than just T,0"

    clock.tick()
    assert len(sock.sent) == before + 1, "a repeat escaped after release"


def test_release_without_a_press_is_harmless(net):
    """_cleanup() sends T,0 on pause even when nothing was held."""
    network, sock, clock = net
    network.clear_held_throttle()
    assert sock.sent[-1][0] == "T,0"
    assert not clock.intervals


def test_only_one_timer_regardless_of_repeated_presses(net):
    """Two timers would send T,100 twice per tick."""
    network, sock, clock = net
    network.set_held_throttle(100)
    network.set_held_throttle(100)
    network.set_held_throttle(100)
    assert len(clock.intervals) == 1

    before = len(sock.sent)
    clock.tick()
    assert len(sock.sent) == before + 1


def test_announce_sends_our_ip_to_the_car(net):
    """The car has to learn our address or telemetry goes nowhere."""
    network, sock, _ = net
    network.announce_car_addr()
    msg, addr = sock.sent[-1]
    assert msg == "H,192.168.1.200"
    assert addr == ("192.168.1.200", 5005)


def test_announce_follows_a_changed_car_ip(net, monkeypatch):
    """Handshake is only useful if it tracks the configured address."""
    network, sock, _ = net
    monkeypatch.setattr(network, "_car_addr_list", ["10.0.0.42", 5005])
    network.announce_car_addr()
    assert sock.sent[-1][0] == "H,10.0.0.42"


def test_announce_survives_a_dead_car(net):
    """An offline car must not crash the UI thread."""
    network, sock, _ = net

    def boom(*_args):
        raise OSError("network unreachable")

    sock.sendto = boom
    network.announce_car_addr()  # must not raise


def test_keepalive_survives_a_dead_car(net):
    """A send failure mid-hold must not take the app down."""
    network, sock, clock = net
    network.set_held_throttle(100)

    def boom(*_args):
        raise OSError("network unreachable")

    sock.sendto = boom
    clock.tick()  # must not raise


def test_protocol_matches_the_firmware():
    """Both sides have to agree on the wire format."""
    firmware = (SRC.parent / "rcar.py").read_text()
    client = (SRC / "network.py").read_text()

    assert 'parts[0] == "H"' in firmware, "firmware does not accept the handshake"
    assert 'f"H,{addr[0]}"' in client, "client does not send the handshake"
    assert "PORT = 5005" in firmware
    assert "PORT_RECV = 5005" in client