"""Battery display widget for Kivy — shows car battery percentage"""

from kivy.uix.label import Label


class Battery(Label):
    """Kivy battery widget — shows car battery percentage
    
    Args:
        state: The shared State object (from state.py) containing batt_pct
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.state = None  # Will be set from main_kivy.py
        
        # Default display
        self.text = "Car: 0%"
        self.font_size = 18
        self.size_hint_x = 1.0
        self.size_hint_y = None
        self.height = 25
        self.background_color = (0.2, 0.2, 0.2)
        self.color = (1, 1, 1)  # White by default
        
    def update(self):
        """Update display based on current battery state"""
        if self.state:
            car_pct = self.state.batt_pct
            
            # Color changes below 20% (same as pygame version)
            if car_pct < 20:
                self.color = (1, 0, 0)  # Red
            else:
                self.color = (1, 1, 1)  # White
            
            self.text = f"Car: {car_pct:.0f}%"
