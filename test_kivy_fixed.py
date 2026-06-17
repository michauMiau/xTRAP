"""Test Kivy RC client — cross-platform (Android, PC, Steam Deck)
REQUIRES SDL2-devel for Linux to work properly.
Install on RPM-ostree: rpm-ostree install copr:<copr-name> SDL2-devel
Then: pip uninstall -y kivy && pip install kivy[base]
"""

import os
import threading
from math import pi

# Force SDL2 backend (Kivy uses sdl2 not SDL2)
os.environ["KIVY_WINDOW"] = "sdl2"

import kivy
kivy.require("2.3.0")
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.utils import get_color_from_rgb as color

# --- NETWORK (same as pygame version) ---
class Network:
    def __init__(self):
        self.sock = None
        self.addr = "192.168.1.171"  # default Cardputer IP
        
    def connect(self, ip):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(1.0)
            self.addr = ip
            return True
        except Exception as e:
            print(f"Connect failed: {e}")
            return False
            
    def send_cmd(self, cmd):
        if not self.sock or not self.addr:
            return False
        try:
            self.sock.sendto(cmd.encode(), (self.addr, 9001))
            return True
        except Exception as e:
            print(f"Send failed: {e}")
            return False

    def receive(self):
        if not self.sock:
            return None
        try:
            data, _ = self.sock.recvfrom(4096)
            return data.decode().strip()
        except socket.timeout:
            return None
        except Exception as e:
            print(f"Receive failed: {e}")
            return False

import socket
network = Network()


class RCClientApp(App):
    steer_value = 180.0
    throttle_value = 0.0
    
    def build(self):
        self.title = "RC Control Center"
        
        layout = FloatLayout(size_hint_x=None, size_hint_y=None)
        
        # --- IP Address Input (top left) ---
        ip_box = BoxLayout(orientation="horizontal", size_hint=(None, None), pos_hint={"center_x": 0.15, "y": 0.85})
        ip_box.add_widget(Label(text="IP:", font_size=24, color=color("white"), bold=True))
        
        self.ip_input = TextInput(
            text="192.168.1.171",
            multiline=False,
            readonly=True if not network.sock else False,
            size_hint_x=0.5,
            font_size=24,
            background_color=(0.3, 0.3, 0.3, 1),
            foreground_color=(1, 1, 1)  # Use foreground_color for text color in Kivy >= 2.x
        )
        ip_box.add_widget(self.ip_input)
        
        self.connect_btn = Button(
            text="CONNECT",
            size_hint_x=0.35,
            font_size=24,
            background_color=(1, 0, 0, 1),
            color=color("white")
        )
        ip_box.add_widget(self.connect_btn)
        self.connect_btn.bind(on_press=self.do_connect)
        
        layout.add_widget(ip_box)
        
        # --- Connection status (top right) ---
        self.status_label = Label(
            text="STATUS: DISCONNECTED",
            font_size=20,
            color=color("orange"),
            bold=True,
            size_hint_x=None,
            width=250
        )
        self.status_label.pos_hint = {"x": 0.68, "y": 0.85}
        layout.add_widget(self.status_label)
        
        # --- Steering display (left side) ---
        steer_box = BoxLayout(orientation="vertical", size_hint=(None, None), pos_hint={"center_x": 0.15, "y": 0.4})
        steer_box.size = (300, 200)
        
        self.steer_display = TextInput(
            text=f"{self.steer_value:.0f}",
            multiline=False,
            readonly=True,
            size_hint_x=1,
            font_size=36,
            background_color=(0.3, 0.3, 0.3, 1),
            foreground_color=(1, 1, 1)
        )
        steer_box.add_widget(self.steer_display)
        
        # Steering buttons (left/right arrows)
        btns = BoxLayout(orientation="horizontal", size_hint_y=None, height=60)
        self.left_btn = Button(text="◄", font_size=32, background_color=(0.5, 0.5, 0.5, 1), color=color("white"))
        self.right_btn = Button(text="►", font_size=32, background_color=(0.5, 0.5, 0.5, 1), color=color("white"))
        
        self.left_btn.bind(on_press=self.do_left)
        self.right_btn.bind(on_press=self.do_right)
        
        btns.add_widget(self.left_btn)
        btns.add_widget(self.right_btn)
        steer_box.add_widget(btns)
        
        layout.add_widget(steer_box)
        
        # --- Throttle display (right side) ---
        throttle_box = BoxLayout(orientation="vertical", size_hint=(None, None), pos_hint={"center_x": 0.85, "y": 0.4})
        throttle_box.size = (300, 200)
        
        self.throttle_display = TextInput(
            text=f"{self.throttle_value:.0f}",
            multiline=False,
            readonly=True,
            size_hint_x=1,
            font_size=36,
            background_color=(0.3, 0.3, 0.3, 1),
            foreground_color=(1, 1, 1)
        )
        throttle_box.add_widget(self.throttle_display)
        
        # Throttle buttons (brake/reverse and accelerate)
        tbtns = BoxLayout(orientation="horizontal", size_hint_y=None, height=60)
        self.brake_btn = Button(text="◀ BRAKE", font_size=24, background_color=(1, 0.2, 0.2, 1), color=color("white"))
        self.gas_btn = Button(text="GAS ►", font_size=24, background_color=(0.2, 0.8, 0.2, 1), color=color("white"))
        
        self.brake_btn.bind(on_press=self.do_brake)
        self.gas_btn.bind(on_press=self.do_gas)
        
        tbtns.add_widget(self.brake_btn)
        tbtns.add_widget(self.gas_btn)
        throttle_box.add_widget(tbtns)
        
        layout.add_widget(throttle_box)
        
        # --- Gamepad info (bottom left) ---
        self.gamepad_label = Label(
            text="Gamepad: NOT DETECTED",
            font_size=18,
            color=color("orange"),
            size_hint_x=None,
            width=250
        )
        self.gamepad_label.pos_hint = {"x": 0.05, "y": 0}
        layout.add_widget(self.gamepad_label)
        
        # --- Keyboard instructions (bottom center) ---
        key_info = Label(
            text="Keyboard: W=Gas A=Brake D=Left J=Right",
            font_size=16,
            color=color("gray"),
            size_hint_x=None,
            width=400
        )
        key_info.pos_hint = {"center_x": 0.5, "y": -0.05}
        layout.add_widget(key_info)
        
        # --- Keyboard support (PC only) ---
        Window.bind(on_key_down=self.on_key_down)  # Kivy >=2.x uses on_key_down
        
        return layout

    def do_connect(self, *args):
        ip = self.ip_input.text.strip() if not network.sock else "192.168.1.171"
        success = network.connect(ip)
        
        if success:
            self.status_label.text = f"STATUS: CONNECTED\n{ip}"
            self.status_label.color = color("green")
            
            # Start receive thread
            threading.Thread(target=self.receive_loop, daemon=True).start()
            print("Connected to", ip)
        else:
            self.status_label.text = "STATUS: FAILED"
            self.status_label.color = color("red")

    def do_left(self, *args):
        self.steer_value -= 5.0
        if self.steer_value < 0:
            self.steer_value = 0
        self.update_steer()

    def do_right(self, *args):
        self.steer_value += 5.0
        if self.steer_value > 180:
            self.steer_value = 180
        self.update_steer()

    def do_brake(self, *args):
        self.throttle_value = -100.0
        self.update_throttle()

    def do_gas(self, *args):
        self.throttle_value += 25.0
        if self.throttle_value > 100:
            self.throttle_value = 100
        self.update_throttle()

    def update_steer(self):
        self.steer_display.text = f"{self.steer_value:.0f}"
        network.send_cmd(f"S,{int(round(self.steer_value))}")

    def update_throttle(self):
        self.throttle_display.text = f"{self.throttle_value:.0f}"
        network.send_cmd(f"T,{int(round(self.throttle_value))}")

    def on_key_down(self, window, keycode, text, modifiers):
        """Keyboard controls (PC only)"""
        key, _ = keycode
        
        if key == 113:  # W - Gas up
            self.throttle_value += 25.0
            if self.throttle_value > 100:
                self.throttle_value = 100
            self.update_throttle()
        
        elif key == 97:  # A - Brake / Reverse
            self.throttle_value = -100.0
            self.update_throttle()
            
        elif key == 100:  # D - Steer left
            self.steer_value -= 5.0
            if self.steer_value < 0:
                self.steer_value = 0
            self.update_steer()
        
        elif key == 106:  # J - Steer right
            self.steer_value += 5.0
            if self.steer_value > 180:
                self.steer_value = 180
            self.update_steer()

    def receive_loop(self):
        """Background thread to receive data from robot"""
        while True:
            data = network.receive()
            if isinstance(data, str) and data:
                parts = data.split(",")
                if len(parts) == 2:
                    cmd = parts[0]
                    value = float(parts[1])
                    
                    # Update UI on main thread (Kivy threading rules!)
                    if cmd == "B":  # Battery
                        pass  # TODO: show battery info
                    elif cmd in ("A", "R"):  # Acceleration or other data
                        pass  # TODO: update telemetry

if __name__ == "__main__":
    app = RCClientApp()
    
    # Check if Kivy has a valid window backend loaded
    if Window is None:
        print("ERROR: Kivy failed to initialize any window backend!")
        print("This usually means SDL2 dev headers are missing.")
        print("On RPM-ostree: rpm-ostree install copr:<copr-name> SDL2-devel")
        exit(1)
    
    Window.size = (800, 450)
    app.run()
