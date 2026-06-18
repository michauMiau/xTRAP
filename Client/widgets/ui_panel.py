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

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button as KButton
from kivy.uix.slider import Slider as KSlider
from kivy.uix.textinput import TextInput as KTextInput


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
        
        # Labels for titles (same as pygame version positioning)
        car_ip_label = KButton(
            text="Car IP", font_size=14, size_hint_x=None, width=80,
            background_color=(0.2, 0.2, 0.2), color=(1, 1, 1),
            # Using Button as label placeholder (no event binding)
        )
        
        phone_ip_label = KButton(
            text="Phone IP", font_size=14, size_hint_x=None, width=80,
            background_color=(0.2, 0.2, 0.2), color=(1, 1, 1),
        )
        
        # Car IP input (TextInput — Kivy handles focus/IME natively)
        self.car_ip_input = KTextInput(
            text="192.168.1.174", multiline=False, size_hint_x=None, width=150,
            font_size=14, background_color=(0.3, 0.3, 0.3), color=(1, 1, 1)
        )
        
        # Phone IP input (placeholder — not needed for RC control)
        self.phone_ip_input = KTextInput(
            text="192.168.1.174", multiline=False, size_hint_x=None, width=150,
            font_size=14, background_color=(0.3, 0.3, 0.3), color=(1, 1, 1)
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
        
        self.add_widget(phone_ip_label)
        self.add_widget(self.phone_ip_input)
    
    def _connect(self, *args):
        """Handle connect/disconnect button press"""
        ip = self.car_ip_input.text.strip()
        if not ip:
            print("Enter IP first!")
            return
        
        # TODO: Implement actual connection logic here
        # For now just print the IP for testing
        print(f"Connecting to {ip}...")


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
        
        label = KButton(
            text="Zoom", font_size=14, size_hint_x=None, width=50,
            background_color=(0.2, 0.2, 0.2), color=(1, 1, 1)
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
        
        label = KButton(
            text="Quality", font_size=14, size_hint_x=None, width=60,
            background_color=(0.2, 0.2, 0.2), color=(1, 1, 1)
        )
        
        self.slider = KSlider(min=0, max=1, value=0.5, size_hint_x=None, width=150)
        
        self.add_widget(label)
        self.add_widget(self.slider)
