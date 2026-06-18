"""Main entry point for the RC Control Center — cross-platform (Android/PC/Steam Deck)"""

import os
# Force GL backend for Kivy on Wayland-only systems
os.environ["KIVY_GL_BACKEND"] = "gl"

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button as KButton
from kivy.uix.label import Label

import threading
from state import state
from network import network_loop, send_steering, send_throttle
from widgets.battery import Battery
from widgets.ui_panel import PanelUI

# --- START NETWORK THREAD ---
threading.Thread(target=network_loop, daemon=True).start()


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
        self.battery = Battery()  # Use the Battery widget
        
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
        
        # Bind buttons to send commands via network functions directly
        self.steering_panel.left_btn.bind(on_press=lambda *a: state.__setattr__('steer', 0) and send_steering(0))
        self.steering_panel.right_btn.bind(on_press=lambda *a: state.__setattr__('steer', 180) and send_steering(180))
        
        self.throttle_panel.reverse_btn.bind(on_press=lambda *a: state.__setattr__('throttle', -100) and send_throttle(-100))
        self.throttle_panel.forward_btn.bind(on_press=lambda *a: state.__setattr__('throttle', 100) and send_throttle(100))
        
        # Schedule UI update loop (replaces pygame clock.tick)
        Clock.schedule_interval(self.update_ui, 1/60)  # 60 FPS like original
        
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
    RCControlCenterApp().run()
