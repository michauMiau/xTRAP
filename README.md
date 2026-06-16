# xTRAP — eXtensible Robotic Technic Automation Platform

Remote-controlled LEGO robot built from LEGO Technic, powered by Micropython on a Cardputer (ESP32) with real-time sensor feedback and steering control.

## Architecture

- **Robot** — ESP32 + BMI270 accelerometer + servo for steering + motor controller
- **Client** — Pygame desktop app that displays G-meter, orientation, battery levels and sends steering commands via UDP
- **Host** — Standalone Pygame visualization of sensor data (debugging)

## Quick Start

### Prerequisites

- Python 3.10+ with Pygame (`pip install pygame`)
- ESP32/LeafLabs board flashed with Micropython + Cardputer libraries (bmi270, display, battlevel, etc.)
- WiFi connection between the Cardputer and PC

### Run Client

```bash
cd Client
python main.py
```

The client connects to the robot's IP on port 5006 for steering commands and listens on port 5005 for sensor data.

### Run Host (standalone visualization)

```bash
python "Host.py"
```

### Flash ESP32 Firmware

- `rCar.py` — main firmware: reads accelerometer, sends UDP telemetry, receives steering commands from PC, controls servo
- `Acceleration live recorder.py` — standalone Cardputer app for logging accelerometer data to SD card (ENT = start recording, SPC = pause/resume, ESC = reset)

## Hardware

| Component | Purpose |
|-----------|---------|
| ESP32 / LeafLabs | Main controller on Cardputer |
| BMI270 (I²C) | 6-DoF accelerometer/gyro for orientation + G-force detection |
| Servo (pin 4) | Steering control — receives angle commands from PC |
| Motor controller | Drives motor for movement (work in progress) |
| SD card slot | Logging data to CSV files (`blackbox_*.csv`) |
| Cardputer display + backlight (pin 38) | Visual feedback and headlight LEDs |

## Network Protocol

All communication is over UDP:

- **Client → ESP32**: `S,<angle>` — steering command (0–180 degrees), port 5006
- **ESP32 → Client**: `M,ax,ay,az` — accelerometer data, port 5005
- **ESP32 → Client**: `B,pct` — battery percentage (sent every ~10s), port 5005

## Features

### Current ✅
- Real-time G-meter visualization on PC client
- Steering control via keyboard (←/→ arrows)
- Accelerometer data logging to SD card with crash detection
- Battery level display on both Cardputer and PC client
- Orientation widget showing roll/pitch angle

### In Progress 🚧
- Motor controller integration — motor not yet working, second servo ordered for steering
- Headlight LEDs on Cardputer display (backlight control via PWM)
- Brakes implementation (mechanical or regen braking?)

### Planned 📋
- Live video streaming from robot → PC client
- Force feedback steering wheel support (accelerometer-based)
- Open-source release after hardware stabilization
- Extensible plugin architecture for additional features

## Contributing

Contributions welcome! This project will be open-sourced once the hardware side is fully stable.
