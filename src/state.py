# state.py — shared application state (sensors, battery, steering/throttle)
import threading


class State:
    def __init__(self):
        self._lock = threading.Lock()  # Thread safety for concurrent access

        # IMU sensor data (updated by network recv thread)
        self.ax = 0.0
        self.ay = 0.0
        self.az = 0.0
        self.g = 0.0          # Current G-force magnitude
        self.max_g = 0.0      # Peak G-force recorded

        # Battery levels (updated by network recv thread)
        self.batt_v = 0.0     # Car battery voltage
        self.batt_pct = 0.0   # Car battery percentage (0-100)
        self.phone_pct = 0.0  # Phone battery percentage

        # Steering and throttle (updated by input handlers)
        self.steer = 90       # Default: straight ahead (0-180 degrees)
        self.throttle = 0     # Default: neutral (−100 to +100 percent)


# Global singleton state object — shared across all modules
state = State()