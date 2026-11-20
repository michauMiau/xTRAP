# xTRAP — Architecture Documentation

## Overview

xTRAP (eXtensible Robotic Technic Automation Platform) is a modular, remote-controlled robot built from LEGO Technic. An ESP32 on a Cardputer runs MicroPython firmware as the robot's brain, and hosts the control interface itself: a browser page plus a WebSocket. Any phone or laptop on the same WiFi opens `http://<car-ip>/` and drives.

## System Diagram

```text
┌──────────────┐        WiFi (HTTP + WebSocket)      ┌─────────────────┐
│              │  GET /  ───────────────────────────→ │                 │
│   Cardputer  │                                    │  Browser client │
│              │  ws /ws  S,<angle> / T,<throttle>   │  (phone/PC)     │
│  + ESP32     │  ←───────────────────────────────→ │                 │
│  + Battery   │           B,pct (5s)                │ steering slider │
│  + Servo ×2  │                                    │ throttle slider │
│  + Motor     │                                    │ release button  │
└──────────────┘                                    └─────────────────┘
```

## Components

### 1. Robot — ESP32 Firmware (Cardputer)

#### rcar.py — Main Control Firmware

**Responsibilities:**

- WiFi connection management (`Config` class for SSID/password)
- HTTP server: `GET /` serves `www/index.html`, any other path serves the same page
- WebSocket endpoint `/ws`: commands in, battery telemetry out
- Steering command handling and servo actuation (both servos in lockstep)
- Motor failsafe

**Key Modules:**

| Module | Pin/Address | Purpose |
| ------ | ----------- | ------- |
| WiFi | STA_IF | Station mode, connects to local network |
| I²C | 0 → **GPIO8 SDA / GPIO9 SCL** | Bus for BMI270 accelerometer. Resolved from the firmware's own `mpconfigboard.h` defines (`MICROPY_HW_I2C0_SDA/SCL`), **not** from the bus number — the vendor's stock Cardputer firmware maps `I2C(0)` to GPIO1/2, which would collide with the servos |
| Battery | ADC pin | Reads battery percentage via `battlevel` library |
| Backlight | GPIO38 | PWM-controlled display backlight (screen off by default) |
| Servo (left) | GPIO2 | Steering — hardware PWM, 50Hz |
| Servo (right) | GPIO3 | Steering — driven in lockstep with the left servo; the linkage connects them mechanically |
| Motor IN1 | GPIO6 | MX1508 forward PWM, 500Hz |
| Motor IN2 | GPIO4 | MX1508 reverse PWM, 500Hz |

All of these are declared once in the `PINS` dict at the top of `rcar.py`; the
driver classes read from it, so there are no bare GPIO numbers left in the code.

**Main loop:** one 20ms tick drives the servo step gate, the failsafe check, garbage collection and the socket poll. The HTTP handshake and WebSocket frames are parsed from the poll events, so nothing blocks the loop.

**Motor failsafe:** if no `T,<throttle>` command arrives within `FAILSAFE_MS` (1000ms), the firmware calls `motor.stop()`. Without it a `T,100` latched forever and a dropped WiFi link left the car at full throttle. The check is a plain `time.ticks_diff` comparison against a timestamp, never a sticky flag.

**Network Protocol (WebSocket, text frames):**

- **Inbound:** `S,<angle>` (0–180, both servos), `T,<throttle>` (−100…100), `X` (release servos)
- **Outbound (every 5s):** `B,pct` battery percentage

**Servo Timing:**

```python
pulse_us = 1000 + (angle / 180.0) * 1000   # 1000μs–2000μs
pwm.duty_ns(int(pulse_us * 1000))          # 50Hz frame from the LEDC peripheral
```

The frame is emitted by hardware, so it keeps running after the servo reaches its target — that is what gives it holding torque when idle. It must **not** be replaced by repeated one-shot pulses, and the pulse must stay inside the 1ms..2ms window hobby servos accept. `X` drops the frame (duty 0) so a parked robot draws no hold current; the next `S` writes the pulse again.

The slew is 2° per 20ms tick (~100°/s), below the servo's rated speed, because faster slews pulled enough stall current through the steering linkage to sag the battery rail and reset the ESP32.

#### Acceleration Live Recorder — Data Logging Mode

A standalone Cardputer app that logs accelerometer data to SD card (used when IMU telemetry is disabled):

- **ENT key** → Start recording (creates `blackbox_NNN.csv` on `/sd/`)
- **SPC key** → Pause/resume logging
- **ESC key** → Reset device
- Records: timestamp_ms, ax, ay, az, g_total, event_type
- Crash detection via G-force threshold (`ACCIDENT_THRESHOLD`, currently undefined — needs to be set)

### 2. Client — Browser Page (`www/index.html`)

A single self-contained page served by the car: steering slider, throttle slider, release button, battery readout and a connection indicator. It connects to `ws://<car-ip>/ws`, sends `S,`/`T,` on input and `X` on the release button, and renders `B,` telemetry. Arrow keys steer and set throttle on desktop.

## Data Flow

### Steering (User → Robot)

1. User drags the steering slider (or presses ←/→)
2. Page sends `S,<angle>` over the WebSocket
3. Firmware calls `servo.set_angle(angle)` and `servo_2.set_angle(angle)`
4. Servo writes the PWM pulse (1000μs–2000μs) and slews 2° per tick

### Battery (Robot → User)

1. Firmware reads `batt.read_pct()` every 5s
2. Sends `B,<pct>` over the WebSocket
3. Page updates the battery readout

### Local Accelerometer Logging (Robot → SD Card)

1. Flash the Acceleration live recorder firmware on Cardputer
2. Press ENT to start recording — creates `blackbox_NNN.csv` on `/sd/`
3. Records timestamp, accelerometer data, G-force, and crash events locally

## Extensibility Points

1. **IMU telemetry** — send `M,ax,ay,az` frames alongside `B,pct`; the page can render a G-meter
2. **Video streaming** — a separate phone streams video; the page can embed it
3. **Force feedback** — a wheel client sends `F,<force>`; the firmware can map it to steering
4. **New commands** — `handle_text()` is the single place a frame becomes an action

## Known Issues / TODOs

1. **Servo on GPIO3 has never been driven on the bench** — the pin is wired and the firmware steps it with the GPIO2 servo, but the mechanical result is unverified
2. **Brakes not implemented** — needs mechanical brake solution or regen braking via motor controller
3. **Single client** — a second browser replaces the first; no multi-operator support
