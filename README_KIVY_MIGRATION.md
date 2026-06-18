# Kivy Migration — What Was Lost from Pygame Version

This documents features from the original pygame client that were NOT ported to Kivy yet.

## ❌ Not Ported (Pominięte)

### 1. G-Meter Widget (g_meter.py)
- **Original**: Circular gauge with red dot tracking acceleration on X/Y axes
- **Why skipped**: User requested — "pomiń portowanie kodu orientacji i g_meter"
- **How to re-implement**: Copy `widgets/g_meter.py` and convert pygame draw calls to Kivy canvas instructions

### 2. Orientation Widget (orientation.py)
- **Original**: Rotating triangle showing roll angle based on accelerometer Y/Z data
- **Why skipped**: User requested — "pomiń portowanie kodu orientacji i g_meter"
- **How to re-implement**: Copy `widgets/orientation.py` and convert pygame Surface/polygon/transform.rotate to Kivy canvas drawing

## ⚠️ Partially Ported (Częściowo zaimplementowane)

### 3. Throttle Control
- **Original**: Not implemented in pygame version (only keyboard-based steering existed)
- **Kivy status**: Button bindings added (◀ reverse, ► throttle forward), but `send_throttle()` not wired to network yet
- **What's needed**: Connect button presses to `network.send_throttle()` function

### 4. Gamepad Controller Support
- **Original**: `pygame._sdl2.controller.init()` + no gamepad mapping (just keyboard)
- **Kivy status**: Kivy handles gamepads natively via SDL2 — no extra init needed
- **What's needed**: Map gamepad axes to steering/throttle in future

### 5. IP Management with Connection Logic
- **Original**: TextBox widget with manual IME handling (pygame.key.start_text_input/stop_text_input) for Car IP and Phone IP
- **Kivy status**: Kivy TextInput handles IME natively — basic text input ready
- **What's needed**: Connect/disconnect button logic + real network connection state tracking

## 🔧 Already Ported (Zaimplementowane w Kivy)

### ✅ Battery Display
- Replaced pygame font rendering + surface blitting with Kivy Label widget
- Color logic preserved: red below 20%, white otherwise

### ✅ Steering Input
- Replaced `pygame.key.get_pressed()` with Kivy Button bindings
- Left button → send_steering(0) (full left), Right button → send_steering(180) (full right)

### ✅ Network Layer
- No changes — business logic stays identical (UDP communication, state updates)

### ✅ State Management
- Added `state.steer` and `state.throttle` attributes to State class for Kivy UI tracking

## 📝 Technical Notes

### Why Kivy was chosen over alternatives:
- Pygame requires SDL2 system libraries on Fedora (libsdl2-devel) — doesn't work well in rpm-ostree environments
- Kivy works with pip-only installation, runs on Android/PC/Steam Deck without extra deps
- Kivy handles gamepad input natively via SDL2 underneath

### Known Issues:
- MTDev import crash on Wayland-only systems (patched with fake module)
- EGL backend failure (fixed by setting `KIVY_GL_BACKEND=gl`)
- Unknown kwargs in widget constructors cause Cython EventDispatcher crashes — avoid passing non-property kwargs to Kivy widgets
