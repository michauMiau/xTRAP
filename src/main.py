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
from kivy.uix.textinput import TextInput

from state import state
import network as net
import settings
from widgets.battery import Battery
from widgets.ui_panel import PanelUI
from input import setup_button_bindings, setup_joystick, release_throttle, release_steer

log = logging.getLogger(__name__)


class StatusPanel(BoxLayout):
    """Status bar — battery + G-meter (horizontal layout)"""

    def __init__(self, on_set_ip=None):
        super().__init__()

        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 30

        # Battery display
        self.battery = Battery()  # Use the Kivy Battery widget

        # G-meter text
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


class IPPanel(BoxLayout):
    """IP configuration panel — input + save button"""

    def __init__(self, on_set_ip=None):
        super().__init__()

        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 40

        self.ip_input = TextInput(
            text=settings.get_car_ip(),
            hint_text="Car IP",
            size_hint_x=0.7,
            font_size=18,
            multiline=False
        )

        save_btn = KButton(
            text="Save",
            size_hint_x=0.3,
            font_size=18,
            background_color=(0.2, 0.5, 0.2, 1),
            color=(1, 1, 1, 1)
        )
        save_btn.bind(on_press=lambda *a: self._save_ip())

        self.add_widget(self.ip_input)
        self.add_widget(save_btn)

    def _save_ip(self):
        ip = self.ip_input.text.strip()
        if not ip or not settings.set_car_ip(ip):
            return
        net.set_car_addr((ip, 5005))
        log.info(f"Car IP set to: {ip}")
        if on_set_ip and callable(on_set_ip):
            on_set_ip(ip)


class SteeringPanel(BoxLayout):
    """Kivy version of the steering input — uses buttons"""

    def __init__(self):
        super().__init__()

        # Horizontal layout: [left_btn] [center_btn] [steer_display] [right_btn]
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 60

        # Left/Right buttons for steering (touch/PC) - ASCII arrows < >
        self.left_btn = KButton(
            text="<", font_size=32, size_hint_x=None, width=45,
            background_color=(0.25, 0.25, 0.25, 1), color=(1, 1, 1, 1)
        )

        # Center steering button — returns steering to 90°
        self.center_btn = KButton(
            text="|", font_size=32, size_hint_x=None, width=45,
            background_color=(0.25, 0.25, 0.25, 1), color=(1, 1, 1, 1)
        )

        # Right/Right buttons for steering (touch/PC) - ASCII arrows < >
        self.right_btn = KButton(
            text=">", font_size=32, size_hint_x=None, width=45,
            background_color=(0.25, 0.25, 0.25, 1), color=(1, 1, 1, 1)
        )

        # Steering display — centered between buttons
        self.steer_display = Label(
            text=f"Steering: {state.steer}°",
            font_size=24,
            size_hint_x=5, width=100
        )

        self.add_widget(self.left_btn)
        self.add_widget(self.center_btn)
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
            size_hint_x=5, width=100
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

        # IP display at bottom — PanelUI from widgets handles car IP + phone IP input
        self.ui_panel = PanelUI()
        self.add_widget(self.ui_panel)


class RCControlCenterApp(App):
    """Main Kivy application — cross-platform RC control center"""
    def __init__(self):
        super().__init__()

        # Responsive window size based on screen dimensions
        Window.size = (min(800, Window.width), min(200, Window.height))

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
        Clock.schedule_interval(self.update_ui, 1/40)  # ~40fps

        net.network_loop()

        # Setup joystick/gamepad support
        setup_joystick()


    def on_stop(self):
        """Clean up when app exits — reset throttle and steer."""
        self._cleanup()

    def on_pause(self):
        """Called when app is minimized/backgrounded (mobile)."""
        self._cleanup()
        return True  # Allow Kivy to keep state on pause

    def _cleanup(self):
        """Release control surfaces before exit/pause."""
        release_throttle()
        release_steer()


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