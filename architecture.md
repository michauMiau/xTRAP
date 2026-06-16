# xTRAP — Architecture Documentation

## Overview

xTRAP (eXtensible Robotic Technic Automation Platform) is a modular, remote-controlled robot built from LEGO Technic. The system uses an ESP32 board mounted on a Cardputer handheld device with Micropython firmware as the robot's brain. A Pygame desktop application serves as the control center, providing real-time sensor visualization and steering input via keyboard or joystick.

## System Diagram

```
┌──────────────┐           UDP          ┌─────────────────┐
│              │  S,<angle> ←──────────→ │                 │
│   Cardputer  │                        │    PC Client    │
│              │  B,pct →────────────── │  (Pygame)       │
│  + ESP32     │                        │ Orientation     │
│  + Battery   │                        │ Battery         │
│  + Servo     │                        │ Steering Input  │
└──────────────┘                        └─────────────────┘
```

## Components

### 1. Robot — ESP32 Firmware (Cardputer)

The robot runs Micropython on an ESP32/LeafLabs board mounted inside the Cardputer. Two firmware variants exist:

#### rcar.py — Main Control Firmware

**Responsibilities:**
- WiFi connection management (`Config` class for SSID/password)
- Steering command reception and servo actuation
- Battery level telemetry broadcast via UDP

> **Note:** IMU (accelerometer) data sending is currently disabled to prevent feature creep. The robot only sends battery level over UDP. Accelerometer logging is available locally on the Cardputer's SD card.

**Key Modules:**
| Module | Pin/Address | Purpose |
|--------|-------------|---------|
| WiFi | STA_IF | Station mode, connects to local network |
| I²C | 0 | Bus for BMI270 accelerometer (local use only) |
| Battery | ADC pin | Reads battery percentage via `battlevel` library |
| Backlight | Pin 38 | PWM-controlled display backlight (screen off by default) |
| Servo | Pin 4 | Steering — writes pulse width based on received angle |

**Network Protocol:**
- **Inbound (polling):** Listens on port 5005 for `S,<angle>` steering commands
- **Outbound (every ~5s):** `B,pct` battery percentage sent via UDP to PC IP:5005

**Servo Timing:**
```python
pulse = int(500 + (angle / 180) * 2000)  # 500μs–2500μs range
# Sends 3 pulses per command with 20ms spacing for reliability
```

#### Acceleration Live Recorder — Data Logging Mode

A standalone Cardputer app that logs accelerometer data to SD card (used when IMU telemetry is disabled):

- **ENT key** → Start recording (creates `blackbox_NNN.csv` on `/sd/`)
- **SPC key** → Pause/resume logging
- **ESC key** → Reset device
- Records: timestamp_ms, ax, ay, az, g_total, event_type
- Crash detection via G-force threshold (`ACCIDENT_THRESHOLD`, currently undefined — needs to be set)

### 2. Client — Pygame Desktop Application

A Pygame-based control center running on the PC. It connects to the robot via UDP and provides visualization + input handling.

#### Directory Structure
```
Client/
├── main.py          # Entry point, event loop, widget rendering
├── state.py         # Shared mutable state (sensors, battery)
├── network.py       # UDP communication layer
├── input.py         # Keyboard/joystick steering input
├── rcar.py          # Robot firmware source code for reference
└── widgets/
    ├── g_meter.py   # Circular G-force visualization
    ├── orientation.py # Roll/pitch angle display
    ├── battery.py    # Battery level text (car + phone)
    └── ui_panel.py  # UI panel for controls/info
```

#### Communication Flow

**Receiving Telemetry (network_loop thread):**
1. Binds to UDP port 5005, drains buffer continuously
2. Parses messages: `B,pct` → update battery state

> **Note:** The client currently receives only battery percentage telemetry. IMU data (`M,ax,ay,az`) sending from the robot is disabled in rcar.py — accelerometer visualization widgets (G-meter, orientation) will show zeros until IMU telemetry is re-enabled.

**Sending Steering Commands:**
- Keyboard input via left/right arrow keys (`STEER_STEP = 2°`)
- Angle clamped to 0–180 range
- Only sends when angle changes (optimizes network traffic)
- Sends `S,<angle>` to CAR_ADDR:5006

#### Widget Rendering

| Widget | Function |
|--------|----------|
| GMeter | Red dot moving within circle, scaled by ax/ay normalized to G-force (currently shows zeros — IMU data disabled) |
| Orientation | Shows roll/pitch angle derived from accelerometer data (currently shows zeros — IMU data disabled) |
| BatteryText | Displays car battery %, low-battery warning in red (<20%) |

## Data Flow

### Steering (User → Robot)

1. User presses ←/→ key on PC keyboard
2. `input.py` calculates new angle, clamps to [0,180]
3. `network.py` sends `S,<angle>` via UDP to ESP32 IP:5006
4. ESP32 receives command, calls `servo.set_angle(angle)`
5. Servo writes PWM pulse (500μs–2500μs) based on angle

### Telemetry (Robot → User) — Currently Disabled

1. Robot reads accelerometer: `ax, ay, az = imu.acceleration`
2. **This is currently disabled** — commented out in rcar.py to prevent feature creep
3. When re-enabled: would send UDP packet `M,{ax},{ay},{az}` to PC IP:5005

### Battery Level (Robot → User)

1. ESP32 reads battery percentage every ~5s: `batt.read_pct()`
2. Sends UDP packet: `B,{pct},0` to PC IP:5005
3. Client updates state.batt_pct, battery widget displays with color coding (red if <20%)

### Local Accelerometer Logging (Robot → SD Card)

1. Flash Acceleration live recorder.py firmware on Cardputer
2. Press ENT to start recording — creates `blackbox_NNN.csv` on `/sd/`
3. Records timestamp, accelerometer data, G-force, and crash events locally

## Extensibility Points

The architecture is designed for future growth — here are the planned extension points:

### 1. Re-enable IMU Telemetry
- Uncomment accelerometer sending in rcar.py (currently disabled)
- Client will receive `M,ax,ay,az` packets again
- G-meter and orientation widgets become functional

### 2. Video Streaming
- A separate phone streaming video to the computer
- Client uses another program (like mpv/vlc) to display video
- Currently planned but not implemented

### 3. Force Feedback Steering Wheel
- Accelerometer-based force feedback from wheel rotation sensor
- ESP32 reads encoder/IMU on steering wheel, sends `F,<force>` to PC client
- Client drives USB force feedback device (e.g., Logitech G29 via HID)
- Provides realistic resistance during steering

### 4. Plugin Architecture
- `Client/widgets/` — modular widget system, each feature adds a new widget class
- `rcar.py` — command parsing can be extended with new message types (`E,<cmd>`, `M2,<motor_data>`)
- Designed for future sensors (distance sensors, cameras, etc.)


## Known Issues / TODOs

1. **Motor controller not working** — i'm planning to fix this
4. **WiFi IP hardcoded** as `192.168.1.8` — should be configurable or auto-discovered
5. **Brakes not implemented** — needs mechanical brake solution or regen braking via motor controller
