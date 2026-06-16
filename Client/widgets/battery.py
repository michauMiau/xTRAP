import pygame
class BatteryText:
    def __init__(self, x, y, font):
        self.x = x
        self.y = y
        self.font = font

    def draw(self, surface, state):
        # --- CARDPUTER ---
        car_pct = state.batt_pct
        car_color = (255,0,0) if car_pct < 20 else (255,255,255)

        car_text = self.font.render(
            f"Car: {car_pct:.0f}%",
            True, car_color
        )

        # --- PHONE (placeholder) ---
        phone_pct = state.phone_pct if state.phone_pct else 75  # default
        charging = False  # placeholder

        phone_color = (255,0,0) if phone_pct < 20 else (255,255,255)

        charge_symbol = "⚡" if charging else ""

        phone_text = self.font.render(
            f"Phone: {phone_pct:.0f}% {charge_symbol}",
            True, phone_color
        )

        # --- DRAW ---
        surface.blit(phone_text, (self.x, self.y))
        surface.blit(car_text, (self.x, self.y + 20))
