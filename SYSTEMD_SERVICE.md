# DMX to OSC Bridge - Systemd Service Documentation

## Overview

The `dmx-osc-bridge.service` ensures that the presence detection system starts
automatically when the Raspberry Pi boots, and restarts automatically if it crashes.

### What the service does

1. Waits 10 seconds for RNBO runner to be ready
2. Runs presence_sensor.py (reads DMX, sends OSC to RNBO)
3. Auto-restarts on failure (after 5 seconds)
4. Logs to journal for debugging

## Useful Commands

| Command                                   | Description                    |
|-------------------------------------------|--------------------------------|
| sudo systemctl status dmx-osc-bridge      | Check if service is running    |
| sudo systemctl start dmx-osc-bridge       | Start the service              |
| sudo systemctl stop dmx-osc-bridge        | Stop the service               |
| sudo systemctl restart dmx-osc-bridge     | Restart the service            |

## Viewing Logs

| Command                                        | Description             |
|------------------------------------------------|-------------------------|
| journalctl -u dmx-osc-bridge -f                | Live log (follow mode)  |
| journalctl -u dmx-osc-bridge -n 50             | Last 50 log lines       |
| journalctl -u dmx-osc-bridge --since "1 hour ago" | Logs from last hour  |

## Troubleshooting

### Service keeps restarting
Check logs: journalctl -u dmx-osc-bridge -n 30

Common causes:
- Enttec not connected (no /dev/ttyUSB0)
- RNBO not running: sudo systemctl status rnbooscquery
- Wrong serial port: ls /dev/ttyUSB*

### Permission denied on serial port
sudo chmod 666 /dev/ttyUSB0

Or permanent fix:
sudo usermod -a -G dialout pi
(then reboot)

### Check if Enttec is detected
ls /dev/ttyUSB*

## Service File Location

/etc/systemd/system/dmx-osc-bridge.service

## Script Location

/home/pi/presence_sensor.py
