"""Kivy RC client — works on Android, PC, Steam Deck."""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.core.window import Window
from kivy.clock import Clock
import socket

CAR_ADDR = ('192.168.1.171', 5001)
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_cmd(cmd):
    udp_sock.sendto(f"{cmd}".encode(), CAR_ADDR)
    print(f">>> {cmd}")

# --- Keyboard handler (WASD / arrows) ---
def on_key_down(instance, key_code):
    """Kivy built-in keyboard event — works on PC."""
    if key_code == 104:   # A / left arrow
        send_cmd("S,90")
    elif key_code == 105:  # D / right arrow
        send_cmd("S,180")
    elif key_code == 26:   # W (up arrow)
        send_cmd("T,75")
    elif key_code == 38:   # S (down arrow — brake/reverse)
        send_cmd("T,-25")

# --- Gamepad handler (works on Android/Steam Deck) ---
gamepad_active = False

def on_gamepad_axis(gamepad, axis_id, value):
    """Gamepad axis event — Kivy handles it natively."""
    global gamepad_active
    if not gamepad_active:
        gamepad_active = True
        print(f"Gamepad connected")

    # Axis 0 = left stick X (steering)
    if axis_id == 0:
        angle = int(value * 90 + 90)  # Map -1..1 → 0..180
        send_cmd(f"S,{angle}")

    # Axis 2 = right trigger (throttle forward), Axis 3 = left trigger (reverse)
    if axis_id == 2 and value > 0.1:
        send_cmd(f"T,{int(value * 100)}")
    elif axis_id == 3 and value < -0.1:
        send_cmd(f"T,-{int(abs(value) * 100)}")

def on_gamepad_button(gamepad, button_id, pressed):
    """Gamepad button event."""
    # Button mapping — configurable per gamepad
    if not pressed:
        return  # Only fire on press
    if button_id == 320:   # A / Cross button = forward (throttle)
        send_cmd("T,100")
    elif button_id == 308:  # X / Square = reverse
        send_cmd("T,-100")

# --- UI ---
class RCClient(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [20, 10]
        self.spacing = 10

        # IP input row
        ip_layout = BoxLayout(size_hint_y=0.15, spacing=10)
        self.ip_input = TextInput(
            text="192.168.1.171", multiline=False, size_hint_x=0.7
        )
        ip_layout.add_widget(self.ip_input)

        btn_layout = BoxLayout(size_hint_x=0.3, spacing=5)
        connect_btn = Button(text="POŁĄCZ")
        connect_btn.bind(on_press=self.connect)
        btn_layout.add_widget(connect_btn)
        stop_btn = Button(text="STOP")
        stop_btn.bind(on_press=lambda *a: send_cmd("S,180,T,0"))
        btn_layout.add_widget(stop_btn)
        ip_layout.add_widget(btn_layout)
        self.add_widget(ip_layout)

        # Steering — touch buttons for mobile + display
        steer_layout = BoxLayout(size_hint_y=0.25, spacing=10)
        left_btn = Button(text="◄")
        left_btn.bind(on_press=lambda *a: send_cmd("S,90"))
        steer_layout.add_widget(left_btn)

        self.steer_display = TextInput(
            text="180", multiline=False, readonly=True, size_hint_x=0.5,
            font_size=24, background_color=(0.3, 0.3, 0.3, 1), color=(255, 255, 255)
        )
        steer_layout.add_widget(self.steer_display)

        right_btn = Button(text="►")
        right_btn.bind(on_press=lambda *a: send_cmd("S,180"))
        steer_layout.add_widget(right_btn)
        self.add_widget(steer_layout)

        # Throttle — touch buttons + display
        throttle_layout = BoxLayout(size_hint_y=0.25, spacing=10)
        rev_btn = Button(text="◀", background_color=(1, 0.3, 0.3))
        rev_btn.bind(on_press=lambda *a: send_cmd("T,-100"))
        throttle_layout.add_widget(rev_btn)

        self.throttle_display = TextInput(
            text="---", multiline=False, readonly=True, size_hint_x=0.5,
            font_size=24, background_color=(1, 1, 0.3, 1), color=(0, 0, 0)
        )
        throttle_layout.add_widget(self.throttle_display)

        fwd_btn = Button(text="▶", background_color=(0.3, 1, 0.3))
        fwd_btn.bind(on_press=lambda *a: send_cmd("T,100"))
        throttle_layout.add_widget(fwd_btn)
        self.add_widget(throttle_layout)

        # Status bar
        status = BoxLayout(size_hint_y=0.1)
        self.status_label = TextInput(
            text="STATUS: Niepołączony", multiline=False, readonly=True, color=(255, 255, 255), font_size=16
        )
        status.add_widget(self.status_label)
        self.add_widget(status)

    def connect(self, *args):
        car_ip = self.ip_input.text.strip()
        if not car_ip:
            return
        global CAR_ADDR
        try:
            send_cmd("P")  # Ping — placeholder command
            self.status_label.text = f"STATUS: Połączony z {car_ip}"
            print(f"Connected to {car_ip}")
        except Exception as e:
            self.status_label.text = f"ERROR: {e}"

# --- MAIN ---
if __name__ == '__main__':
    Window.bind(on_key_down=on_key_down)  # Keyboard (PC only, Kivy 2.x)

    app = App()
    rc = RCClient()

    # Register gamepad — Kivy 2.3+ automatic gamepad handling
    try:
        from kivy.core.window import Window as Win
        for gp in Win.get_gamepads():
            on_gamepad_axis(gp, None, None)  # Trigger connection event
    except Exception:
        print("No gamepad detected")

    app.run()
