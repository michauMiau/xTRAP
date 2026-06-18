"""Kivy RC client test — minimal cross-platform (Android/PC/Steam Deck)"""

import os
# Must set BEFORE any Kivy imports!
os.environ["SDL_VIDEODRIVER"] = "wayland"  # Use Wayland video driver instead of x11

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.utils import get_color_from_hex as color

# --- UDP setup (same as pygame client) ---
import socket, threading, time

car_addr = {"ip": "192.168.1.171", "port": 4000}
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
connected = False


def send_cmd(cmd):
    """Send UDP command to Cardputer"""
    if not connected:
        print("Not connected!")
        return
    try:
        sock.sendto(cmd.encode(), (car_addr["ip"], car_addr["port"]))
        print(f"Sent: {cmd}")
    except Exception as e:
        print(f"Send error: {e}")


def network_loop():
    """Listen for telemetry from Cardputer"""
    global connected
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode()
            if msg.startswith("B,"):  # Battery: B,pct
                pct = int(msg.split(",")[1])
                print(f"Battery: {pct}%")
            elif msg.startswith("A,"):  # Acceleration: A,ax,ay,az
                ax, ay, az = map(float, msg.split(","))
                print(f"Accel: G={ax:.2f},{ay:.2f},{az:.2f}")
        except Exception as e:
            print(f"Recv error: {e}")
            time.sleep(0.1)


def connect_to_car():
    global connected
    addr = ip_input.text.strip()
    if not addr:
        print("Enter IP first!")
        return
    car_addr["ip"] = addr
    try:
        sock.sendto(b"HELLO", (car_addr["ip"], car_addr["port"]))
        time.sleep(0.2)  # Wait for response
        connected = True
        connect_btn.text = "DISCONNECT"
        print(f"Connected to {addr}")
    except Exception as e:
        print(f"Connect error: {e}")


def disconnect_car():
    global connected
    connected = False
    connect_btn.text = "CONNECT"
    print("Disconnected")


# --- Kivy UI ---

class RCClient(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = 10
        self.spacing = 5

        # Top row: IP input + connect button
        top_row = BoxLayout(size_hint_y=0.1, spacing=5)
        
        self.ip_input = TextInput(
            text="192.168.1.171",
            multiline=False,
            size_hint_x=0.7,
            font_size=20,
            background_color=(0.3, 0.3, 0.3),
        )
        self.ip_input.hint_text = "Cardputer IP"
        
        global connect_btn
        connect_btn = Button(
            text="CONNECT",
            size_hint_x=0.3,
            font_size=18,
            background_color=color("#4CAF50"),
        )
        connect_btn.bind(on_press=self._connect)
        
        top_row.add_widget(self.ip_input)
        top_row.add_widget(connect_btn)
        self.add_widget(top_row)

        # Steering display (read-only)
        self.steer_display = TextInput(
            text="Steering: 180°",
            multiline=False,
            readonly=True,
            size_hint_y=0.05,
            font_size=24,
            background_color=(0.3, 0.3, 0.3),
        )

        # Steering buttons (touch/keyboard)
        steer_row = BoxLayout(size_hint_y=0.15, spacing=10)
        
        self.steer_left_btn = Button(
            text="◄", font_size=48, size_hint_x=0.35,
            background_color=color("#2196F3"),
        )
        self.steer_right_btn = Button(
            text="►", font_size=48, size_hint_x=0.35,
            background_color=color("#2196F3"),
        )
        
        # Throttle buttons
        throttle_row = BoxLayout(size_hint_y=0.15, spacing=10)
        
        self.reverse_btn = Button(
            text="◀", font_size=48, size_hint_x=0.35,
            background_color=color("#F44336"),  # Red for reverse/brake
        )
        self.forward_btn = Button(
            text="►", font_size=48, size_hint_x=0.35,
            background_color=color("#4CAF50"),  # Green for forward
        )

        # Status label
        status_label = TextInput(
            text="Status: Disconnected",
            multiline=False,
            readonly=True,
            size_hint_y=0.08,
            font_size=16,
            background_color=(0.2, 0.2, 0.2),
        )

        # Add widgets in order
        self.add_widget(status_label)
        self.add_widget(self.steer_display)
        self.add_widget(steer_row)
        self.add_widget(throttle_row)

        # Bind buttons to send commands
        self.steer_left_btn.bind(on_press=lambda *a: send_cmd("S,0"))  # full left
        self.steer_right_btn.bind(on_press=lambda *a: send_cmd("S,180"))  # full right
        
        self.reverse_btn.bind(on_press=lambda *a: send_cmd("T,-100"))  # reverse/brake
        self.forward_btn.bind(on_press=lambda *a: send_cmd("T,100"))  # throttle forward

    def _connect(self, *_):
        if connected:
            disconnect_car()
        else:
            connect_to_car()


# --- Main App ---

class RCApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.1)
        client = RCClient()
        
        # Start network listener thread
        threading.Thread(target=network_loop, daemon=True).start()
        
        return client


if __name__ == "__main__":
    RCApp().run()
