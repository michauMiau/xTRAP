"""Main entry point for the RC Control Center — cross-platform (Android/PC/Steam Deck)"""

import os
import sys
# Detect optimal Kivy GL backend (respect user override if set)
if not os.environ.get("KIVY_GL_BACKEND"):
    # Wayland-only systems need desktop OpenGL, not EGL
    has_x11 = bool(os.environ.get("DISPLAY") or "x11" in sys.platform)
    if not has_x11:
        os.environ["KIVY_GL_BACKEND"] = "gl"

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button as KButton
from kivy.uix.label import Label

import threading
from state import state
from network import _start_network_loop, disconnect
from widgets.battery import Battery
from widgets.ui_panel import PanelUI
from input import setup_button_bindings


class StatusPanel(BoxLayout):
    """Status bar — battery + G-meter (horizontal layout)"""
    
    def __init__(self):
        super().__init__()
        
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 30
        
        # Battery display
        self.battery = Battery()  # Use the Kivy Battery widget
        
        # G-meter text (from original main.py — keeps the G calculation logic from state)
        self.g_label = Label(
            text=f"G: {state.g:.2f} MAX: {state.max_g:.2f}", 
            font_size=18, 
            size_hint=(0.7, None), 
            height=30
        )
        
        # Spacer between battery and G-meter
        spacer = Label(size_hint=(0.15, None), height=30)
        
        self.add_widget(self.battery)
        self.add_widget(spacer)
        self.add_widget(self.g_label)


class SteeringPanel(GridLayout):
    """Kivy version of the steering input — uses buttons"""
    
    def __init__(self):
        super().__init__()
        
        # 3 columns: left button, display, right button
        self.cols = 3
        
        # Left/Right buttons for steering (touch/PC)
        self.left_btn = KButton(text="←", font_size=48, size_hint=(0.5, 1))
        self.right_btn = KButton(text="→", font_size=48, size_hint=(0.5, 1))
        
        # Steering display
        self.steer_display = Label(
            text=f"Steering: {state.steer}°", 
            font_size=24, 
            size_hint_x=None, width=100
        )
        
        self.add_widget(self.left_btn)
        self.add_widget(self.steer_display)
        self.add_widget(self.right_btn)


class ThrottlePanel(GridLayout):
    """Kivy version of the throttle input — uses buttons"""
    
    def __init__(self):
        super().__init__()
        
        # 3 columns: reverse, display, forward
        self.cols = 3
        
        # Reverse/Brake button (left)
        self.reverse_btn = KButton(text="←", font_size=48, size_hint=(0.5, 1))
        
        # Throttle display  
        self.throttle_display = Label(
            text=f"Throttle: {state.throttle}%", 
            font_size=24, 
            size_hint_x=None, width=100
        )
        
        # Forward/Throttle button (right)
        self.forward_btn = KButton(text="→", font_size=48, size_hint=(0.5, 1))
        
        self.add_widget(self.reverse_btn)
        self.add_widget(self.throttle_display)
        self.add_widget(self.forward_btn)


class MainLayout(GridLayout):
    """Main app layout — grid-based, no overlapping elements"""
    
    def __init__(self):
        super().__init__()
        
        # 2 rows: status bar (top), controls (middle), UI panel (bottom)
        self.rows = 3
        
        # Status bar at top (battery + G reading)
        self.status_panel = StatusPanel()
        self.add_widget(self.status_panel)
        
        # Steering and throttle panels side by side in middle row
        control_row = GridLayout()
        control_row.cols = 2  # steering left, throttle right
        
        self.steering_panel = SteeringPanel()
        control_row.add_widget(self.steering_panel)
        
        self.throttle_panel = ThrottlePanel()
        control_row.add_widget(self.throttle_panel)
        
        self.add_widget(control_row)
        
        # IP display at bottom (placeholder — will add real IP management later)
        self.ui_panel = PanelUI()
        self.add_widget(self.ui_panel)


class RCControlCenterApp(App):
    """Main Kivy application — cross-platform RC control center"""
    
    def __init__(self):
        super().__init__()
        
        # Setup window for mobile/PC use — same size as pygame version (800x200)
        Window.size = (800, 200)

    def on_start(self):
        """Start the network receive loop when app starts."""
        _start_network_loop()

    def on_stop(self):
        """Cleanup — stop network thread and close sockets on exit."""
        disconnect()
    
    def build(self):
        return MainLayout()

    def update_ui(self, dt):
        """Update UI elements with current state — called every frame by Clock.schedule_interval"""
        # Update steering display
        self.root.steering_panel.steer_display.text = f"Steering: {state.steer}°"
        
        # Update throttle display
        self.root.throttle_panel.throttle_display.text = f"Throttle: {state.throttle}%"
        
        # Update battery display — red below 20%, white otherwise (same as pygame version)
        car_pct = state.batt_pct
        if car_pct < 20:
            self.root.status_panel.battery.color = (1, 0, 0)  # Red
        else:
            self.root.status_panel.battery.color = (1, 1, 1)  # White
        
        self.root.status_panel.battery.text = f"Car: {car_pct:.0f}%"
        
        # Update G-meter display  
        self.root.status_panel.g_label.text = f"G: {state.g:.2f} MAX: {state.max_g:.2f}"


if __name__ == "__main__":
    app = RCControlCenterApp()
    root = app.build()
    
    # Bind button events from input.py — connect UI to network commands
    setup_button_bindings(root.steering_panel, root.throttle_panel)
    
    # Start UI update loop (called every frame)
    Clock.schedule_interval(app.update_ui, 1/30)  # ~30fps
    
    app.run()
