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
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button as KButton
from kivy.uix.label import Label

import threading
from state import state
from network import _start_network_loop, disconnect
from widgets.battery import Battery
from widgets.ui_panel import PanelUI
from input import setup_button_bindings


class SteeringPanel(FloatLayout):
    """Kivy version of the steering input — uses buttons"""
    
    def __init__(self):
        super().__init__()
        
        self.left_btn = None
        self.right_btn = None
        
        # Left/Right buttons for steering (touch/PC)
        self.left_btn = KButton(text="◄", font_size=48, size_hint=(0.35, 1))
        self.right_btn = KButton(text="►", font_size=48, size_hint=(0.35, 1))
        
        # Steering display
        self.steer_display = Label(
            text=f"Steering: {state.steer}°", 
            font_size=24, 
            size_hint=(0.3, 1)
        )
        
        self.add_widget(self.left_btn)
        self.add_widget(self.steer_display)
        self.add_widget(self.right_btn)


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
        
        self.add_widget(self.reverse_btn)
        self.add_widget(self.throttle_display)
        self.add_widget(self.forward_btn)


class StatusPanel(FloatLayout):
    """Status display — battery, G-meter reading"""
    
    def __init__(self):
        super().__init__()
        
        # Battery display
        self.battery = Battery()  # Use the Kivy Battery widget
        
        # G-meter text (from original main.py — keeps the G calculation logic from state)
        self.g_label = Label(
            text=f"G: {state.g:.2f} MAX: {state.max_g:.2f}", 
            font_size=18, 
            size_hint=(1.0, None), 
            height=25
        )
        
        self.add_widget(self.battery)
        self.add_widget(self.g_label)


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
        
        # IP display at bottom (placeholder — will add real IP management later)
        self.ui_panel = PanelUI()
        self.ui_panel.pos_hint = {"bottom": 0}
        root.add_widget(self.ui_panel)
        
        return root

    def update_ui(self, dt):
        """Update UI elements with current state — called every frame by Clock.schedule_interval"""
        # Update steering display
        self.steering_panel.steer_display.text = f"Steering: {state.steer}°"
        
        # Update throttle display
        self.throttle_panel.throttle_display.text = f"Throttle: {state.throttle}%"
        
        # Update battery display — red below 20%, white otherwise (same as pygame version)
        car_pct = state.batt_pct
        if car_pct < 20:
            self.status_panel.battery.color = (1, 0, 0)  # Red
        else:
            self.status_panel.battery.color = (1, 1, 1)  # White
        
        self.status_panel.battery.text = f"Car: {car_pct:.0f}%"
        
        # Update G-meter display  
        self.status_panel.g_label.text = f"G: {state.g:.2f} MAX: {state.max_g:.2f}"


if __name__ == "__main__":
    app = RCControlCenterApp()
    root = app.build()
    
    # Bind button events from input.py — connect UI to network commands
    setup_button_bindings(app.steering_panel, app.throttle_panel)
    
    # Start UI update loop (called every frame)
    Clock.schedule_interval(app.update_ui, 1/30)  # ~30fps
    
    app.run()
