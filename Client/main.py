"""Main entry point for the RC Control Center — cross-platform (Android/PC/Steam Deck)"""

import os
import sys
from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button as KButton
from kivy.uix.label import Label

import threading
from state import state
import network as net
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


class SteeringPanel(BoxLayout):
    """Kivy version of the steering input — uses buttons"""
    
    def __init__(self):
        super().__init__()
        
        # Horizontal layout: [left_btn] [steer_display] [right_btn]
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 60
        
        # Left/Right buttons for steering (touch/PC) - ASCII arrows < >
        self.left_btn = KButton(
            text="<", font_size=48, size_hint_x=None, width=60,
            background_color=(0.25, 0.25, 0.25, 1), color=(1, 1, 1, 1)
        )
        self.right_btn = KButton(
            text=">", font_size=48, size_hint_x=None, width=60,
            background_color=(0.25, 0.25, 0.25, 1), color=(1, 1, 1, 1)
        )
        
        # Steering display - centered between buttons
        self.steer_display = Label(
            text=f"Steering: {state.steer}°", 
            font_size=24, 
            size_hint_x=None, width=100
        )
        
        self.add_widget(self.left_btn)
        self.add_widget(self.steer_display)
        self.add_widget(self.right_btn)


class ThrottlePanel(BoxLayout):
    """Kivy version of the throttle input — uses buttons"""
    
    def __init__(self):
        super().__init__()
        
        # Horizontal layout: [reverse_btn] [throttle_display] [forward_btn]
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 60
        
        # Reverse/Brake button (left) - ASCII arrow <
        self.reverse_btn = KButton(
            text="<", font_size=48, size_hint_x=None, width=60,
            background_color=(0.25, 0.25, 0.25, 1), color=(1, 1, 1, 1)
        )
        
        # Throttle display  
        self.throttle_display = Label(
            text=f"Throttle: {state.throttle}%", 
            font_size=24, 
            size_hint_x=None, width=100
        )
        
        # Forward/Throttle button (right) - ASCII arrow >
        self.forward_btn = KButton(
            text=">", font_size=48, size_hint_x=None, width=60,
            background_color=(0.25, 0.25, 0.25, 1), color=(1, 1, 1, 1)
        )
        
        self.add_widget(self.reverse_btn)
        self.add_widget(self.throttle_display)
        self.add_widget(self.forward_btn)


class MainLayout(GridLayout):
    """Main app layout — grid-based, no overlapping elements"""
    
    def __init__(self):
        super().__init__()
        
        # 3 rows: status bar (top), controls (middle), UI panel (bottom)
        self.rows = 3
        
        # Status bar at top (battery + G reading) — horizontal layout on top of everything
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

    def build(self):
        """Build the main layout — called by Kivy during initialization."""
        return MainLayout()

    def on_start(self):
        """Start the network receive loop when app starts.
        
        self.root is already set by Kivy at this point, so we can safely access it.
        """
        # Set up button bindings — self.root is now available via Kivy's init
        setup_button_bindings(self.root.steering_panel, self.root.throttle_panel)
        
        # Start UI update loop (called every frame by Clock.schedule_interval)
        Clock.schedule_interval(self.update_ui, 1/30)  # ~30fps
        
        net.network_loop()

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
    app.run()
