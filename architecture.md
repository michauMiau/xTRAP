# xTRAP — Architecture Documentation

## Overview

xTRAP (eXtensible Robotic Technic Automation Platform) is a modular, remote-controlled robot built from LEGO Technic. The system uses an ESP32/LeafLabs board mounted on a Cardputer handheld device with Micropython firmware as the robot's brain. A Pygame desktop application serves as the control center, providing real-time sensor visualization and steering input via keyboard or joystick.

## System Diagram

```
┌──────────────┐           UDP          ┌─────────────────┐
│              │  S,<angle> ←──────────→ │                 │
│   Cardputer  │                        │    PC Client    │
│              │  M,ax,ay,az →─────────→ │  (Pygame)       │
│  + ESP32     │  B,pct →────────────── │                 │
│  + BMI270    │                        │ G-meter         │
│  + Servo     │                        │ Orientation     │
│  + SD card   │                        │ Battery         │
└──────────────┘                        └─────────────────┘
```

## Components

### 1. Robot — ESP32 Firmware (Cardputer)

The robot runs Micropython on an ESP32/LeafLabs board mounted inside the Cardputer. Two firmware variants exist:

#### rCar.py — Main Control Firmware

**Responsibilities:**
- WiFi connection management (`Config` class for SSID/password)
- I²C communication with BMI270 accelerometer at 40Hz
- UDP telemetry broadcast (accelerometer data + battery level)
- Steering command reception and servo actuation

**Key Modules:**
| Module | Pin/Address | Purpose |
|--------|-------------|---------|
| WiFi | STA_IF | Station mode, connects to local network |
| I²C | 0 | Bus for BMI270 accelerometer |
| BMI270 | SDA=2, SCL=1 (Grove port) | Accelerometer/gyro sensor |
| Backlight | Pin 38 | PWM-controlled display backlight |
| Servo | Pin 4 | Steering — writes pulse width based on received angle |

**Network Protocol:**
- **Outbound (every ~20ms):** `M,ax,ay,az` → UDP broadcast to PC IP:5005
- **Inbound (polling):** Listens on port 5005 for `S,<angle>` steering commands
- **Periodic (every ~10s):** `B,pct` battery percentage sent via UDP

**Servo Timing:**
```python
pulse = int(500 + (angle / 180) * 2000)  # 500μs–2500μs range
# Sends 3 pulses per command with 20ms spacing for reliability
```

#### Acceleration Live Recorder — Data Logging Mode

A standalone Cardputer app that logs accelerometer data to SD card:

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
├── widgets/
│   ├── g_meter.py   # Circular G-force visualization
│   ├── orientation.py # Roll/pitch angle display
│   ├── battery.py    # Battery level text (car + phone)
│   └── ui_panel.py  # UI panel for controls/info
```

#### Communication Flow

**Receiving Telemetry (network_loop thread):**
1. Binds to UDP port 5005, drains buffer continuously
2. Parses messages: `M,ax,ay,az` → update accelerometer state; `B,pct` → update battery state
3. Calculates G-force: `g = sqrt(ax² + ay² + (az-9.81)²) / 9.81`

**Sending Steering Commands:**
- Keyboard input via left/right arrow keys (`STEER_STEP = 2°`)
- Angle clamped to 0–180 range
- Only sends when angle changes (optimizes network traffic)
- Sends `S,<angle>` to CAR_ADDR:5006

#### Widget Rendering

| Widget | Function |
|--------|----------|
| GMeter | Red dot moving within circle, scaled by ax/ay normalized to G-force |
| Orientation | Shows roll/pitch angle derived from accelerometer data |
| BatteryText | Displays car battery %, low-battery warning in red (<20%) |

### 3. Host — Standalone Visualization (Debug)

A minimal Pygame app that receives accelerometer data and renders a G-meter:

- Same UDP protocol as Client (`M,ax,ay,az`)
- Simpler rendering — just the circle with dot + text overlay
- Runs on port 5005
- Useful for debugging sensor data independently of the client UI

## Data Flow

### Steering (User → Robot)

1. User presses ←/→ key on PC keyboard
2. `input.py` calculates new angle, clamps to [0,180]
3. `network.py` sends `S,<angle>` via UDP to ESP32 IP:5006
4. ESP32 receives command, calls `servo.set_angle(angle)`
5. Servo writes PWM pulse (500μs–2500μs) based on angle

### Telemetry (Robot → User)

1. ESP32 reads accelerometer every ~20ms: `ax, ay, az = imu.acceleration`
2. Sends UDP packet: `M,{ax},{ay},{az}` to PC IP:5005
3. Client's network_loop thread receives and parses data
4. Calculates G-force and updates shared state object
5. Widgets read from state and render on screen at 60 FPS

### Battery Level (Robot → User)

1. ESP32 reads battery percentage every ~10s: `batt.read_pct()`
2. Sends UDP packet: `B,{pct},0` to PC IP:5005
3. Client updates state.batt_pct, battery widget displays with color coding (red if <20%)

## Extensibility Points

The architecture is designed for future growth — here are the planned extension points:

### 1. Video Streaming
- ESP32 webcam module → MJPEG streaming to PC client over UDP/RTSP
- Client renders video stream as a widget overlay
- Currently planned but not implemented

### 2. Force Feedback Steering Wheel
- Accelerometer-based force feedback from wheel rotation sensor
- ESP32 reads encoder/IMU on steering wheel, sends `F,<force>` to PC client
- Client drives USB force feedback device (e.g., Logitech G29 via HID)
- Provides realistic resistance during steering

### 3. Plugin Architecture
- `Client/widgets/` — modular widget system, each feature adds a new widget class
- `rCar.py` — command parsing can be extended with new message types (`E,<cmd>`, `M2,<motor_data>`)
- Designed for future sensors (distance sensors, cameras, etc.)

### 4. Open Source
- Hardware stabilization phase in progress (motor controller issues)
- Once hardware is reliable, full open-source release planned

## Known Issues / TODOs

1. **Motor controller not working** — user ordered replacement, second servo for steering
2. **ACCIDENT_THRESHOLD undefined** in recorder app — needs a G-force threshold value
3. **Battery percentage hardcoded** in ESP32 (`pct = batt.read_pct()` but variable unused)
4. **WiFi IP hardcoded** as `192.168.1.8` — should be configurable or auto-discovered
5. **Brakes not implemented** — needs mechanical brake solution or regen braking via motor controller
