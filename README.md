# xTRAP — eXtensible Robotic Technic Automation Platform

Remote-controlled driving robot built from Technic (but yours doesn't have to be), powered by MicroPython on a Cardputer (ESP32) with real-time sensor feedback and steering control.

## Architecture

- **RCAR** — ESP32 + BMI270 accelerometer + 2 steering servos + MX1508 motor controller. It joins WiFi and runs a small web server on the car itself.
- **Client** — a browser page served by the car. Open `http://<car-ip>/` on a phone or laptop and you get the controls; commands and telemetry ride one WebSocket (`/ws`). No app to install, no UDP port, no client build.

The old UDP + Kivy client version is preserved on the [`legacy/udp-rcar`](https://github.com/michauMiau/xTRAP/tree/legacy/udp-rcar) branch.

## Quick Start

### Prerequisites

- Cardputer flashed with MicroHydra
- `rcar.py` and `www/index.html` uploaded to the card
- WiFi credentials in the MicroHydra config (`wifi_ssid`, `wifi_pass`)

### Running

The firmware boots, joins WiFi and prints its address:

```
Connected: ('192.168.1.225', '255.255.255.0', ...)
Web control on http://192.168.1.225/ (ws /ws)
```

It is a MicroHydra app: the Cardputer screen shows the car's IP, battery, steering, throttle and link state while it runs. `ENT` releases the steering servos, `SPC` stops the motor, `ESC` recenters the steering.

Open that address in a browser. The page has a steering slider, a throttle slider and a release button; arrow keys work on desktop. Battery telemetry arrives over the same WebSocket every 5s.

## Hardware

| Component | Purpose |
| --------- | ------- |
| ESP32 / MicroPython | Main controller on Cardputer |
| BMI270 (I²C) | 6-DoF accelerometer/gyro for orientation + G-force detection |
| Servo ×2 | Steering — GPIO2 and GPIO3, driven in lockstep (the linkage connects them) |
| Motor controller | MX1508 on GPIO6/GPIO4, 500Hz PWM |

## Protocol

One WebSocket at `ws://<car-ip>/ws`, text frames:

- **Browser → car**: `S,<angle>` — steering 0–180 degrees, both servos in lockstep
- **Browser → car**: `T,<throttle>` — throttle −100…100. The motor stops on its own if no `T` arrives for 1000ms
- **Browser → car**: `X` — release both steering servos: the PWM frame drops, the servos draw no hold current and the wheels settle. Any `S` wakes them again
- **Car → browser**: `B,pct` — battery percentage every 5s

`GET /` serves the control page; any other path gets the same page.

## Features

### Current

- Browser remote with steering, throttle and servo release
- Battery telemetry over WebSocket
- Failsafe motor stop when the link goes quiet
- Servo pulses kept inside the 1ms..2ms window hobby servos accept

### Feature Creep

- Live video streaming from a phone
- Force feedback steering wheel support (accelerometer-based)
- Headlight LED on Cardputer

## Contributing

Contributions welcome!
