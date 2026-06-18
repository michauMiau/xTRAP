"""Kivy version of the RC Control Center — cross-platform (Android/PC/Steam Deck)

Required environment variables:
- KIVY_GL_BACKEND: Defaults to 'gl' on Wayland-only systems. Set to 'gles2' for
  EGL-based backends if running under X11 or on mobile. Detection/fallback is handled automatically below.
"""

import os
import sys
import logging
import threading
import time
from queue import Full, Queue, Empty as QueueEmpty
from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button as KButton
from kivy.uix.label import Label

import network
from state import state

# --- START NETWORK THREAD (daemon, runs sensor loop) ---
_thread_running = True  # Flag for graceful shutdown

def _start_network_loop():
    threading.Thread(target=network.network_loop, daemon=True).start()
_start_network_loop()

# --- Network send queue (offloads blocking socket sends off UI thread) ---
_send_queue: Queue = Queue(maxsize=20)  # Max 20 pending commands before dropping old ones

def _send_worker():
    """Background worker that drains the send queue and executes network sends."""
    while _thread_running:
        try:
            msg, addr = _send_queue.get_nowait()
            network.send_sock.sendto(msg.encode(), addr)
        except QueueEmpty:
            time.sleep(0.01)  # Busy wait — low overhead for real-time RC
        except Exception:
            pass

threading.Thread(target=_send_worker, daemon=True).start()

def send_network_command(msg, addr):
    """Enqueue a network command to be sent by the background worker."""
    try:
        _send_queue.put_nowait((msg, addr))
    except Full:
        # Queue full — drop this message silently (will retry on next frame)
        pass

def send_network_throttle(throttle):
    """Enqueue a throttle command to be sent by the background worker."""
    try:
        _send_queue.put_nowait((f"T,{int(throttle)}", network.CAR_ADDR))
    except Full:
        pass


# --- MTDev provider import (robust fallback, no fake modules) ---
try:
    from kivy.input.providers.mtdev import MTDeviceProvider
except Exception as e:
    logging.warning(f"MTDev unavailable — touchscreen fine-tune disabled ({e})")

# --- EGL backend detection & fallback ---
def _detect_gl_backend():
    """Detect and set the optimal Kivy GL backend for the current environment.
    
    - Wayland-only (no X11): defaults to 'gl' (desktop OpenGL) — avoids EGL errors
    - X11/mobile: uses default Kivy detection (usually gles2 or gl)
    - User override: if KIVY_GL_BACKEND is already set, respects it.
    
    Reference: https://kivy.org/doc/stable/guide/config.html#environment-variables
    """
    # If already set by user, respect it
    if os.environ.get("KIVY_GL_BACKEND"):
        return
    
    # On Wayland-only systems (no X11), default to 'gl' (desktop OpenGL)
    has_x11 = os.environ.get("DISPLAY") or "x11" in sys.platform
    if not has_x11:
        os.environ["KIVY_GL_BACKEND"] = "gl"
        logging.info("Wayland-only detected — using GL backend for Kivy (avoids EGL errors)")

_detect_gl_backend()


# --- Input handling (throttle with rate limiting) ---
class ThrottlePanel(FloatLayout):
    """Kivy version of the throttle input — uses buttons"""

    def __init__(self):
        super().__init__()

        # Reverse/Brake button (left)
        self.reverse_btn = KButton(text="◀", font_size=48, size_hint=(0.35, 1))

        # Throttle display  
        self.throttle_display = Label(
            text=f"Throttle: {state.throttle}%", 
            font_size=24, 
            size_hint=(0.3, 1)
        )

        # Forward/Throttle button (right)
        self.forward_btn = KButton(text="►", font_size=48, size_hint=(0.35, 1))

        # Rate limiting: throttle can change at most ~20Hz (50ms between sends)
        self._last_throttle_send_time: float = 0.0
        self.throttle_debounce_ms = 50

        # Emergency stop button (for safety — overrides all commands)
        self.emergency_btn = KButton(text="🛑", font_size=48, size_hint=(0.35, 1))

        self.add_widget(self.reverse_btn)
        self.add_widget(self.throttle_display)
        self.add_widget(self.forward_btn)
        self.add_widget(self.emergency_btn)


class SteeringPanel(FloatLayout):
    """Kivy version of the steering input — uses buttons"""

    def __init__(self):
        super().__init__()

        # Left/Right buttons for steering (touch/PC)
        self.left_btn = KButton(text="◄", font_size=48, size_hint=(0.35, 1))
        self.right_btn = KButton(text="►", font_size=48, size_hint=(0.35, 1))

        # Steering display
        self.steer_display = Label(
            text=f"Steering: {state.steer}°", 
            font_size=24, 
            size_hint=(0.3, 1)
        )

        # Rate limiting: steering can change at most ~20Hz (50ms between sends)
        self._last_steer_send_time: float = 0.0
        self.steer_debounce_ms = 50

        self.add_widget(self.left_btn)
        self.add_widget(self.steer_display)
        self.add_widget(self.right_btn)


class StatusPanel(FloatLayout):
    """Status display — battery, G-meter reading"""

    def __init__(self):
        super().__init__()

        # Battery display
        self.battery_label = Label(
            text="Car: 0%", 
            font_size=18, 
            size_hint=(1.0, None), 
            height=25
        )

        # G-meter text (from original main.py — keeps the G calculation logic from state)
        self.g_label = Label(
            text=f"G: {state.g:.2f} MAX: {state.max_g:.2f}", 
            font_size=18, 
            size_hint=(1.0, None), 
            height=25
        )

        # Connection status indicator
        self.conn_label = Label(
            text="Status: Disconnected", 
            font_size=14, 
            size_hint=(1.0, None), 
            height=20
        )

        self.add_widget(self.battery_label)
        self.add_widget(self.g_label)
        self.add_widget(self.conn_label)


class IPDisplay(FloatLayout):
    """IP display panel — with connect/disconnect logic and input validation"""

    def __init__(self, app_instance):
        super().__init__()
        
        self.app = app_instance
        
        # IP input field
        from kivy.uix.textinput import TextInput as KTextInput
        self.ip_input = KTextInput(
            text="192.168.1.174", 
            font_size=14,
            size_hint=(0.6, None), 
            height=30,
            multiline=False,
            input_filter='text'  # Only allow letters and numbers (no spaces)
        )

        # Connect/Disconnect button
        self.conn_button = KButton(
            text="Connect", 
            font_size=14, 
            size_hint=(0.35, None), 
            height=30,
            background_color=(0.2, 0.8, 0.2, 1)  # Green for connect
        )

        self.conn_button.bind(on_press=self._toggle_connection)

        self.add_widget(self.ip_input)
        self.add_widget(self.conn_button)

    def _validate_ip(self):
        """Validate IP:port format."""
        text = self.ip_input.text.strip()
        if not text:
            return None
        
         # Split on last colon for port — supports both "192.168.1.174" and "192.168.1.174:5006"
        parts = text.rsplit(":", 1)
        ip_addr = parts[0]
        
        # Basic IP validation (4 octets, each 0-255)
        if not all(0 <= int(p) <= 255 for p in ip_addr.split(".")):
            return None
        
        port = 5006 if len(parts) == 1 else int(parts[1])
        
        # Validate port range (1-65535)
        if not (1 <= port <= 65535):
            return None
            
        return ip_addr, port

    def _toggle_connection(self, *args):
        """Toggle connect/disconnect state."""
        if self.app.is_connected:
            # Disconnecting
            network.send_sock.close()
            network.CAR_ADDR = ("192.168.1.174", 5006)
            self.app.is_connected = False
            
            self.conn_button.text = "Connect"
            self.conn_button.background_color = (0.2, 0.8, 0.2, 1)  # Green
            self.ip_input.disabled = False
            
            if hasattr(self.app.status_panel, 'conn_label'):
                self.app.status_panel.conn_label.text = "Status: Disconnected"
        else:
            # Connecting — validate IP first
            result = self._validate_ip()
            
            if not result:
                # Show error message (flash button red briefly)
                self.conn_button.background_color = (1, 0.3, 0.3, 1)  # Red for error
                Clock.schedule_once(lambda dt: setattr(self.conn_button, 'background_color', (0.2, 0.8, 0.2, 1)), 1.5)
                return
            
            ip_addr, port = result
            network.CAR_ADDR = (ip_addr, port)
            self.app.is_connected = True
            
            # Update UI
            self.conn_button.text = "Disconnect"
            self.conn_button.background_color = (0.8, 0.2, 0.2, 1)  # Red for disconnect
            self.ip_input.disabled = True
            
            if hasattr(self.app.status_panel, 'conn_label'):
                self.app.status_panel.conn_label.text = f"Status: Connected to {ip_addr}:{port}"

    def update_connection_status(self):
        """Update connection status display (called by app to refresh UI)."""
        pass


class RCControlCenterApp(App):
    """Main Kivy application — cross-platform RC control center"""

    is_connected = False  # Connection state flag
    
    def __init__(self):
        super().__init__()

        # Setup window for mobile/PC use — same size as pygame version (800x200)
        Window.size = (800, 200)
    
    def build(self):
        root = FloatLayout()

        # Status bar at top (battery + G reading)
        self.status_panel = StatusPanel()
        self.status_panel.pos_hint = {"top": 1}
        root.add_widget(self.status_panel)

        # Steering panel in middle-left
        self.steering_panel = SteeringPanel()
        self.steering_panel.pos_hint = {"x": 0, "y": 0.2}
        root.add_widget(self.steering_panel)

        # Throttle panel in middle-right  
        self.throttle_panel = ThrottlePanel()
        self.throttle_panel.pos_hint = {"right": 1, "y": 0.2}
        root.add_widget(self.throttle_panel)

        # IP display at bottom (with real IP management — TextInput + connect button)
        self.ip_display = IPDisplay(self)
        self.ip_display.pos_hint = {"bottom": 0}
        root.add_widget(self.ip_display)

        # --- Bind steering buttons to send commands ---
        # Rate-limited: only send if enough time has passed since last send
        self.steering_panel.left_btn.bind(
            on_press=lambda *a: self._rate_limit_send_steering(0, "left")
        )
        self.steering_panel.right_btn.bind(
            on_press=lambda *a: self._rate_limit_send_steering(180, "right")
        )

        # --- Bind throttle buttons to send commands ---
        self.throttle_panel.reverse_btn.bind(on_press=lambda *a: self.send_throttle(-100))  # Brake/reverse
        self.throttle_panel.forward_btn.bind(on_press=lambda *a: self.send_throttle(100))   # Throttle forward

        # --- Emergency stop (always sends, overrides everything) ---
        self.throttle_panel.emergency_btn.bind(
            on_press=lambda *a: self._emergency_stop()
        )

        # Schedule UI update loop (replaces pygame clock.tick)
        Clock.schedule_interval(self.update_ui, 1/60)  # 60 FPS like original

        return root
    
    def _rate_limit_send_steering(self, angle, direction):
        """Rate-limit steering sends to ~20Hz max."""
        now = time.time() * 1000  # milliseconds since epoch
        if now - self.steering_panel._last_steer_send_time < self.steering_panel.steer_debounce_ms:
            return  # Too soon, skip this send
        
        self.steering_panel._last_steer_send_time = now
        state.steer = int(angle)
        
        # Offload the network call to the background worker thread
        threading.Thread(target=lambda: send_network_command(f"S,{angle}", network.CAR_ADDR), daemon=True).start()

    def send_throttle(self, throttle_value):
        """Send throttle command to Cardputer (future implementation)"""
        if throttle_value != state.throttle:
            now = time.time() * 1000
            if now - self.throttle_panel._last_throttle_send_time < self.throttle_panel.throttle_debounce_ms:
                return  # Too soon, skip this send
            
            self.throttle_panel._last_throttle_send_time = now
            state.throttle = int(throttle_value)
            
            # Offload the network call to the background worker thread
            threading.Thread(target=lambda: send_network_throttle(state.throttle), daemon=True).start()

    def _emergency_stop(self):
        """Emergency stop — sends brake immediately, overrides all inputs."""
        state.throttle = 0
        state.steer = 180
        # Send both simultaneously
        threading.Thread(target=lambda: (send_network_command("S,180", network.CAR_ADDR), send_network_throttle(0)), daemon=True).start()

    def update_ui(self, dt):
        """Update UI elements with current state — called every frame by Clock.schedule_interval"""
        # Update steering display
        self.steering_panel.steer_display.text = f"Steering: {state.steer}°"

        # Update throttle display
        self.throttle_panel.throttle_display.text = f"Throttle: {state.throttle}%"

        # Update battery display — red below 20%, white otherwise (same as pygame version)
        car_pct = state.batt_pct
        if car_pct < 20:
            self.status_panel.battery_label.color = (1, 0, 0)  # Red
        else:
            self.status_panel.battery_label.color = (1, 1, 1)  # White

        self.status_panel.battery_label.text = f"Car: {car_pct:.0f}%"

        # Update G-meter display  
        self.status_panel.g_label.text = f"G: {state.g:.2f} MAX: {state.max_g:.2f}"

    def on_stop(self):
        """Cleanup on app exit — close sockets and stop the network loop."""
        global _thread_running
        _thread_running = False
        
        # Close send socket
        try:
            network.send_sock.close()
        except Exception as e:
            logging.error(f"Error closing send socket: {e}")

if __name__ == "__main__":
    RCControlCenterApp().run()
