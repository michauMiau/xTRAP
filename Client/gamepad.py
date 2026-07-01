"""Gamepad (controller) input handling via SDL2.

Uses the same SDL2 that Kivy already bundles, so no extra dependencies are needed.
Works on Linux with any SDL2 gamepad API controller (Xbox, PS4/PS5, Steam Controller, etc.).
"""

import os
from ctypes import cdll, c_int, c_float, POINTER, cast, Structure, sizeof, byref
import atexit

# --- Configuration: steering deadzone and range ---
STEER_DEADZONE = 0.15       # Left stick X deadzone (fractional)
STEER_RANGE_MAX = 135        # Absolute max steering angle from center (90 ± STEER_RANGE_MAX)

# --- SDL2 constants ---
SDL_CONTROLLER_AXIS_LEFTX = 0
SDL_CONTROLLER_AXIS_LEFTY = 1
SDL_CONTROLLER_AXIS_RIGHTX = 2
SDL_CONTROLLER_AXIS_RIGHTY = 3
SDL_CONTROLLER_AXIS_TRIGGERLEFT = 4      # R2 (right trigger, forward throttle)
SDL_CONTROLLER_AXIS_TRIGGERRIGHT = 5     # L2 (left trigger, reverse/brake)
SDL_CONTROLLER_BINDTYPE_NONE = 0
SDL_CONTROLLER_BINDTYPE_BUTTON = 1
SDL_CONTROLLER_BINDTYPE_AXIS = 2

# --- SDL2 bindings ---
_sdl2_path = None

def _find_sdl2():
    global _sdl2_path
    if _sdl2_path:
        return _sdl2_path
    
    # Path where Kivy bundles its own SDL2 (so the app works standalone)
    kivy_lib_dir = os.path.join(os.path.dirname(__file__), '..', 'Kivy.libs')
    for name in os.listdir(kivy_lib_dir):
        if name.startswith('libSDL2-2-d9872e50'):
            _sdl2_path = os.path.join(kivy_lib_dir, name)
            return _sdl2_path
    
    # System SDL2 as fallback (Steam Deck / Linux desktop)
    system = None
    for p in ('/usr/lib/x86_64-linux-gnu', '/lib/x86_64-linux-gnu'):
        candidate = os.path.join(p, 'libSDL2-2.0.so.0')
        if os.path.isfile(candidate):
            system = candidate
            break
    
    _sdl2_path = system or kivy_lib_dir
    return _sdl2_path

_sdl2_cdll = None

def sdl2():
    global _sdl2_cdll
    if _sdl2_cdll:
        return _sdl2_cdll
    path = _find_sdl2()
    try:
        _sdl2_cdll = cdll.LoadLibrary(path)
    except OSError:
        _sdl2_cdll = None
    return _sdl2_cdll

# --- Controller state ---
class _GamepadState:
    running = False
    controllers = []       # list of (SDL_GameController*, guid_str, name, axes)
    deadzone = STEER_DEADZONE
    steer_range_max = STEER_RANGE_MAX

def init_gamepad():
    """Initialize SDL2 gamepad subsystem. Call once at app startup."""
    state = _GamepadState()
    if not sdl2():
        return False
    
    dll = sdl2()
    # Check SDL_Init availability first (returns 0 on success, non-zero means already initialized)
    err = dll.SDL_Init(1 << 5)  # SDL_INIT_GAMECONTROLLER
    if err != 0:
        return False
    
    state.running = True
    _scan_controllers()
    
    def cleanup():
        for ctrl in reversed(state.controllers):
            handle = ctrl[0]
            dll.SDL_GameControllerClose(handle)
        dll.SDL_Quit()
    
    atexit.register(cleanup)
    return True

def _scan_controllers():
    state = _GamepadState()
    if not sdl2():
        return
    
    dll = sdl2()
    count = dll.SDL_NumJoysticks()
    
    for i in range(count):
        # Check if this joystick has a controller mapping
        name = dll.SDL_GameControllerNameForIndex(i)
        if not name:
            continue
        
        ctrl = dll.SDL_GameControllerOpen(i)
        if ctrl:
            guid_bytes = bytes(32)
            guid_ptr = cast(guid_bytes, POINTER(c_int))
            # SDL_JoystickGetGUID returns 16 bytes as int* (4 ints), not 32
            guid_data = (c_int * 8)()
            joystick = dll.SDL_GameControllerGetJoystick(ctrl)
            guid = dll.SDL_JoystickGetGUID(joystick)
            
            state.controllers.append((ctrl, None, name, [0.0] * 6))

def update_gamepad(dt=1/30):
    """Poll all controllers and return (steer_angle, throttle)."""
    if not _GamepadState.running or not sdl2():
        return None
    
    state = _GamepadState()
    dll = sdl2()
    
    # Refresh controller list
    count = dll.SDL_NumJoysticks()
    new_controllers = []
    for i in range(len(state.controllers)):
        ctrl, guid_str, name, axes = state.controllers[i]
        joystick = dll.SDL_GameControllerGetJoystick(ctrl)
        
        if not dll.SDL_JoystickGetConnected(joystick):
            dll.SDL_GameControllerClose(ctrl)
            continue
        
        # Update controller list (keep existing controllers alive)
        new_controllers.append((ctrl, guid_str, name, axes))
    
    state.controllers = new_controllers
    
    steer_angle = None
    throttle = 0.0
    
    for ctrl, guid_str, name, _ in state.controllers:
        # Left stick X (axis 0) — steering
        left_x = dll.SDL_GameControllerGetAxis(ctrl, SDL_CONTROLLER_AXIS_LEFTX) / 32768.0
        
        deadzone = state.deadzone
        if abs(left_x) < deadzone:
            left_x = 0.0
        else:
            # Apply smooth deadzone curve
            sign = 1.0 if left_x > 0 else -1.0
            t = (abs(left_x) - deadzone) / (1.0 - deadzone)
            left_x = sign * (t ** 2)  # square for smoother feel
        
        steer_angle = 90 + int(left_x * state.steer_range_max)
        
        # Right trigger (L2 in SDL naming — forward throttle 0..-100%)
        right_trigger = dll.SDL_GameControllerGetAxis(ctrl, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) / 32768.0
        if right_trigger > 0.5:
            t = ((right_trigger - 0.5) * 2.0) ** 2  # square curve
            throttle -= int(t * 100)
        
        # Left trigger (R2 in SDL naming — reverse / brake 0..+100%)
        left_trigger = dll.SDL_GameControllerGetAxis(ctrl, SDL_CONTROLLER_AXIS_TRIGGERLEFT) / 32768.0
        if left_trigger > 0.5:
            t = ((left_trigger - 0.5) * 2.0) ** 2
            throttle += int(t * 100)
    
    return steer_angle, throttle
