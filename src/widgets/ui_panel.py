"""UI Panel for Kivy — IP management widget (replaces pygame custom widgets)

Original (pygame) had:
1. Button class → Custom rect drawing + mouse event handling
2. Slider class → Custom rectangle + circle knob dragging
3. TextBox class → Custom text input with cursor animation

In Kivy:
- Use kivy.uix.button.Button for buttons
- Use kivy.uix.slider.Slider for sliders
- Use kivy.uix.textinput.TextInput for text input

"""

import socket
import threading
from kivy.clock import Clock as KClock
from kivy.network.urlrequest import UrlRequest
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button as KButton
from kivy.uix.slider import Slider as KSlider
from kivy.uix.textinput import TextInput as KTextInput
from kivy.uix.label import Label as KLabel


class PanelUI(BoxLayout):
    """Simplified UIPanel for IP management (replaces pygame's UIPanel)

    Original pygame UIPanel had:
    - 4 buttons (Flash, Front, Back, Focus) — camera controls, not needed
    - 2 sliders (Zoom, Quality) — camera controls, not needed
    - 2 text inputs (Car IP, Phone IP) — only Car IP is relevant

    Kivy version keeps only the essential: Car IP input + connect button.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 60

        # Labels for titles (replaced Button with Label — no event binding needed)
        car_ip_label = KLabel(
            text="Car IP", font_size=14, size_hint_x=None, width=80
        )

        phone_ip_label = KLabel(
            text="Phone IP", font_size=14, size_hint_x=None, width=80
        )

        # Car IP input (TextInput — Kivy handles focus/IME natively)
        self.car_ip_input = KTextInput(
            text="192.168.1.225", multiline=False, size_hint_x=None, width=150,
            font_size=14, background_color=(0.3, 0.3, 0.3), foreground_color=(1, 1, 1, 1)
        )

        # Phone IP input (placeholder — not needed for RC control)
        self.phone_ip_input = KTextInput(
            text="192.168.1.174", multiline=False, size_hint_x=None, width=150,
            font_size=14, background_color=(0.3, 0.3, 0.3), foreground_color=(1, 1, 1, 1)
        )

        # Status label for connection feedback
        self.status_label = KLabel(
            text="", font_size=12, size_hint_x=None, width=80
        )

        # Connect button (replaces pygame's TextBox ENTER key handling)
        self.connect_btn = KButton(
            text="CONNECT", font_size=14, size_hint_x=None, width=80,
            background_color=(0.29, 0.76, 0.31, 1), color=(1, 1, 1, 1)
        )

        self.add_widget(car_ip_label)
        self.add_widget(self.car_ip_input)
        self.connect_btn.bind(on_press=self._connect)
        self.add_widget(self.connect_btn)
        self.add_widget(self.status_label)

        self.add_widget(phone_ip_label)
        self.add_widget(self.phone_ip_input)

    def _connect(self, *args):
        """Handle connect button press — trust user input, set address directly."""
        import network as net
        
        ip = self.car_ip_input.text.strip()
        
        # Parse IP:port or just IP (default port 5005)
        if ":" in ip:
            parts = ip.rsplit(":", 1)
            try:
                addr_tuple = (parts[0], int(parts[1]))
            except ValueError:
                self._show_status("INVALID FORMAT", (1, 0.3, 0.3, 1))
                return
        else:
            # Basic validation — just check it's not empty and has dots
            if "." not in ip or len(ip) < 7:
                self._show_status("INVALID IP", (1, 0.3, 0.3, 1))
                return
            addr_tuple = (ip, 5005)
        
        net.set_car_addr(addr_tuple)
        self._show_status(f"CONNECTED TO {addr_tuple[0]}", (0.3, 1, 0.3, 1))

    def _show_status(self, text, color):
        """Update status label with text and color"""
        self.status_label.text = text
        self.status_label.color = color


class ZoomSlider(BoxLayout):
    """Zoom slider — Kivy Slider (replaces pygame custom Slider class)

    Original pygame version had a manual implementation with:
    - Custom rect drawing
    - Circle knob rendering
    - Mouse drag event handling

    Kivy version uses built-in Slider widget.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 30

        label = KLabel(
            text="Zoom", font_size=14, size_hint_x=None, width=50
        )

        self.slider = KSlider(min=0, max=1, value=0.5, size_hint_x=None, width=150)

        self.add_widget(label)
        self.add_widget(self.slider)


class QualitySlider(BoxLayout):
    """Quality slider — Kivy Slider (replaces pygame custom Slider class)"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 30

        label = KLabel(
            text="Quality", font_size=14, size_hint_x=None, width=60
        )

        self.slider = KSlider(min=0, max=1, value=0.5, size_hint_x=None, width=150)

        self.add_widget(label)
        self.add_widget(self.slider)
