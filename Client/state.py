# state.py
# Stores the current state of sensors or whatever

class State:
    def __init__(self):
        self.ax = 0
        self.ay = 0
        self.az = 0
        self.g = 0
        self.max_g = 0
        self.batt_v = 0
        self.batt_pct = 0
        self.phone_pct = 0
state = State()