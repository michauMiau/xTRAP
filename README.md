# xTRAP — eXtensible Robotic Technic Automation Platform

Remote-controlled driving robot built from Technic (but yours doesn't have to be), powered by Micropython on a Cardputer (ESP32) with real-time sensor feedback and steering control.

## Architecture

- **RCAR** — ESP32 + BMI270 accelerometer + servo for steering + motor controller
- **Client** — Pygame desktop app that displays G-meter, orientation, battery levels and sends steering commands via UDP

## Quick Start

### Prerequisites

- Python 3.10+ with Pygame (`pip install pygame`)
- SDL2 Libraries for Pygame
- ESP32 board flashed with Micropython + Cardputer libraries (bmi270, display, battlevel, etc.)
- WiFi connection between the Cardputer and PC

The client connects to the robot's IP on port 5006 for steering commands and listens on port 5005 for sensor data.

### Running on the Cardputeer

- `rcar.py` — main firmware: reads accelerometer, sends UDP telemetry, receives steering commands from PC, controls servo
- `Acceleration live recorder.py` — standalone Cardputer app for testing the accelerometer

## Hardware

| Component | Purpose |
| --------- | ------- |
| ESP32 / Micropython | Main controller on Cardputer |
| BMI270 (I²C) | 6-DoF accelerometer/gyro for orientation + G-force detection |
| Servo (pin 4) | Steering control — receives angle commands from PC |
| Motor controller | Drives motor for movement |

## Network Protocol

All communication is over raw UDP:

- **Client → ESP32**: `S,<angle>` — steering command (0–180 degrees), port 5006
- **ESP32 → Client**: `M,ax,ay,az` — accelerometer data, port 5005
- **ESP32 → Client**: `B,pct` — battery percentage (sent every ~10s), port 5005

## Features

### Current ✅

- Real-time G-meter visualization on PC client
- Steering control via keyboard (←/→ arrows)
- Battery level display on both Cardputer and PC client
- Orientation widget showing roll/pitch angle

### In Progress 🚧

- Motor acceleration
- Brakes implementation (mechanical or regen braking?)

### Feature Creep 📋

- Live video streaming from a Phone
- Force feedback steering wheel support (accelerometer-based)
- Headlight LED on Cardputer
- Controlling the video streaming phone
  
## Contributing

Contributions welcome!
