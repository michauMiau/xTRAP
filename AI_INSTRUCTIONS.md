# AI Instructions — xTRAP

## Naming Conventions (CRITICAL)
- **NO framework-specific names** — never prefix widget classes with the framework name (e.g., NO `BatteryKivy`, NO `PanelUIKivy`)
- Names should describe the **function/purpose**, not the implementation:
  - ✅ `Battery` (battery display widget)
  - ✅ `ZoomSlider` (zoom slider)
  - ❌ `BatteryKivy` (framework-specific)
  - ❌ `ZoomSliderKivy` (framework-specific)

## Architecture — Strict Separation of Concerns
- **main.py** — Kivy App init, widget creation, button bindings. NO business logic.
- **input.py** — Input handling (keyboard/gamepad/touch) + sending commands to network module. Contains `on_steer_left`, `on_steer_right`, `on_throttle_reverse`, `on_throttle_forward`.
- **network.py** — UDP socket management, send_steering/send_throttle functions, receive loop. NO UI logic.

## Logging
- Centralized in main.py (global logger) — don't define separate loggers in every module unless absolutely necessary.

## Kivy Property Names (CRITICAL)
Kivy widget properties differ from what you might expect:
- `foreground_color` (NOT `color`) — for text/label colors
- `background_color` — for background colors
- Never pass unknown kwargs to Kivy widgets (e.g., `color` on TextInput will crash with "Properties ['color'] passed to init may not be existing property names")
