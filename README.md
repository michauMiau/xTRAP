# xTRAP — eXtensible Robotic Technic Automation Platform

Remote-controlled LEGO robot built from LEGO Technic, powered by Micropython on a Cardputer (ESP32) with real-time sensor feedback and steering control.

## Architecture

- **Robot** — ESP32 + Battery monitor + servo for steering (IMU data logging locally to SD card)
- **Client** — Pygame desktop app that displays G-meter, orientation, battery levels and sends steering commands via UDP
- ~~Host~~ — Standalone Pygame visualization of sensor data — **DELETED**, superseded by Client

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

### Flash ESP32 Firmware

- **rcar.py** — main firmware: receives steering commands from PC, controls servo, sends battery level via UDP
- **Acceleration live recorder.py** — standalone Cardputer app for logging accelerometer data to SD card (ENT = start recording, SPC = pause/resume, ESC = reset)

## Hardware

| Component | Purpose |
|-----------|---------|
| ESP32 / LeafLabs | Main controller on Cardputer |
| Battery monitor (ADC) | Reads battery percentage via battlevel library |
| Servo (pin 4) | Steering control — receives angle commands from PC |
| Motor controller | Drives motor for movement (work in progress) |
| SD card slot | Logging data to CSV files (`blackbox_*.csv`) |

## Network Protocol

All communication is over UDP:

- **Client → ESP32**: `S,<angle>` — steering command (0–180 degrees), port 5006
- **ESP32 → Client**: `B,pct` — battery percentage (sent every ~5s), port 5005

> IMU data (`M,ax,ay,az`) sending from the robot is currently disabled to prevent feature creep. Accelerometer logging is available locally on the Cardputer's SD card via the Acceleration live recorder app.

## Features

### Current ✅
- Real-time G-meter visualization on PC client (currently shows zeros — IMU data disabled)
- Steering control via keyboard (←/→ arrows)
- Battery level display on PC client (low-battery warning in red <20%)
- Orientation widget on PC client (currently shows zeros — IMU data disabled)

### In Progress 🚧
- Motor controller integration — motor not yet working, second servo ordered for steering
- Headlight LEDs on Cardputer display (backlight control via PWM)
- Brakes implementation (mechanical or regen braking?)

### Planned 📋
- Re-enable IMU telemetry (G-meter and orientation widgets will become functional)
- Live video streaming from robot → PC client
- Force feedback steering wheel support (accelerometer-based)
- Open-source release after hardware stabilization
- Extensible plugin architecture for additional features

## Contributing

Contributions welcome! This project will be open-sourced once the hardware side is fully stable.
