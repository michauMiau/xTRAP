"""UI Panel for Kivy — IP management widget (replaces pygame custom widgets)

Original (pygame) had:
1. Button class → Custom rect drawing + mouse event handling
2. Slider class → Custom rectangle + circle knob dragging  
3. TextBox class → Custom text input with cursor animation
   
In Kivy:
- Use kivy.uix.button.Button for buttons
- Use kivy.uix.slider.Slider for sliders
- Use kivy.uix.textinput.TextInput for text input

Since we only need IP address management (no camera controls), this is simplified.
"""

from kivy.clock import Clock as KClock
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
            text="192.168.1.174", multiline=False, size_hint_x=None, width=150,
            font_size=14, background_color=(0.3, 0.3, 0.3), foreground_color=(1, 1, 1)
        )
        
        # Phone IP input (placeholder — not needed for RC control)
        self.phone_ip_input = KTextInput(
            text="192.168.1.174", multiline=False, size_hint_x=None, width=150,
            font_size=14, background_color=(0.3, 0.3, 0.3), foreground_color=(1, 1, 1)
        )
        
        # Status label for connection feedback
        self.status_label = KLabel(
            text="", font_size=12, size_hint_x=None, width=80
        )
        
        # Connect button (replaces pygame's TextBox ENTER key handling)
        self.connect_btn = KButton(
            text="CONNECT", font_size=14, size_hint_x=None, width=80,
            background_color=(0.29, 0.76, 0.31), color=(1, 1, 1)
        )
        
        self.add_widget(car_ip_label)
        self.add_widget(self.car_ip_input)
        self.connect_btn.bind(on_press=self._connect)
        self.add_widget(self.connect_btn)
        self.add_widget(self.status_label)
        
        self.add_widget(phone_ip_label)
        self.add_widget(self.phone_ip_input)
    
    def _validate_ip(self, ip_str):
        """Validate IP:port format. Returns (ip, port) tuple or None if invalid."""
        try:
            parts = ip_str.rsplit(":", 1)
            ip_addr = parts[0]
            
            # Basic IP validation (4 octets, each 0-255)
            if not all(0 <= int(p) <= 255 for p in ip_addr.split(".")):
                return None
            
            port = 5006 if len(parts) == 1 else int(parts[1])
            
            # Validate port range (1-65535)
            if not (1 <= port <= 65535):
                return None
                
            return ip_addr, port
        except ValueError:
            return None
    
    def _connect(self, *args):
        """Handle connect/disconnect button press"""
        import network
        
        ip = self.car_ip_input.text.strip()
        if not ip:
            self.status_label.text = "ERROR"
            self.status_label.color = (1, 0.3, 0.3)
            return
        
        result = self._validate_ip(ip)
        
        if not result:
            # Show error — flash red briefly
            self.status_label.text = "INVALID IP"
            self.status_label.color = (1, 0.3, 0.3)
            KClock.schedule_once(lambda dt: setattr(self.status_label, 'text', ''), 2)
            return
        
        ip_addr, port = result
        network.CAR_ADDR = (ip_addr, port)
        
        try:
            # Try to connect — sends a PING to verify connection
            network.send_sock.sendto(b"PING", (ip_addr, port))
            
            self.status_label.text = "CONNECTED"
            self.status_label.color = (0.3, 1, 0.3)
        except Exception as e:
            self.status_label.text = "FAILED"
            self.status_label.color = (1, 0.3, 0.3)


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
