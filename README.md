# xTRAP — eXtensible Robotic Technic Automation Platform

Remote-controlled driving robot built from Technic (but yours doesn't have to be), powered by Micropython on a Cardputer (ESP32) with real-time sensor feedback and steering control.

## Architecture

- **RCAR** — ESP32 + BMI270 accelerometer + servo for steering + motor controller
- **Client** — Pygame desktop app that displays G-meter, orientation, battery levels and sends steering commands via UDP

## Quick Start

### Prerequisites

- Python 3.10+ with Pygame (`pip install kivy`)
- GL libraries for Kivy
- Cardputer board flashed with MicroHydra
- WiFi connection between the Cardputer and PC

The client sends commands to the robot on port 5005 (the firmware binds the same port for both directions) and receives telemetry on the same socket.

### Running on the Cardputeer

- `rcar.py` — main firmware: receives `S`/`T` commands over UDP, drives both
  steering servos (GPIO2 + GPIO3, in lockstep) and the MX1508 motor
  (GPIO6/GPIO4), and sends battery telemetry. Stops the motor if no throttle
  command arrives for 1000ms.

## Hardware

| Component | Purpose |
| --------- | ------- |
| ESP32 / Micropython | Main controller on Cardputer |
| BMI270 (I²C) | 6-DoF accelerometer/gyro for orientation + G-force detection |
| Servo ×2 | Steering — GPIO2 and GPIO3, driven in lockstep (the linkage connects them) |
| Motor controller | Drives motor for movement |

## Network Protocol

All communication is over raw UDP:
- **Client → ESP32**: `S,<angle>` — steering command (0–180 degrees), port 5005
- **Client → ESP32**: `T,<throttle>` — throttle −100…100, port 5005. The motor stops on its own if no `T` arrives for 1000ms
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
- Brakes implementation (set throttle to 0 or slight reverse?)

### Feature Creep 📋

- Live video streaming from a Phone
- Force feedback steering wheel support (accelerometer-based)
- Headlight LED on Cardputer
- Controlling the video streaming phone
  
## Contributing

Contributions welcome!
