# Purple Rain

An interactive audiovisual installation for Copenhagen Light Festival 2026.

**Festival:** Copenhagen Light Festival 2026  
**Dates:** January 31 - February 23, 2026  
**Location:** Amager Bio, Copenhagen

## Concept

Purple Rain explores themes of water, flooding, and climate change through contrasting soundscapes. Visitors step beneath a suspended cylinder of liquid organza fabric, illuminated by custom LED light bars and gobo projectors.

- **Empty installation:** Dystopian soundscape plays
- **Visitor present:** Audio crossfades to utopian soundscape

The transition creates an intimate, transformative experience - suggesting that human presence and engagement can shift our relationship with climate futures.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENCE DETECTION                                │
│                                                                             │
│    LD2410C Radar ──► Arduino + DMX Shield ──► DMX Universe 1               │
│    (Presence Sensor)   (Master Controller)     (10-15m cable)              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ DMX Signal (Channel 1: 0=absent, 1=present)
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│         LIGHTING SYSTEM         │   │          AUDIO SYSTEM           │
│                                 │   │                                 │
│  • Custom LED Light Bars        │   │  Enttec DMX USB Pro             │
│  • 2x Gobo Projectors           │   │         │                       │
│    ("water lamps")              │   │         ▼                       │
│                                 │   │  Raspberry Pi 5                 │
│  Controlled directly by         │   │  + HiFiBerry DAC8x              │
│  Arduino via DMX                │   │         │                       │
│                                 │   │         ▼                       │
│                                 │   │  RNBO Audio Engine              │
│                                 │   │  (Crossfade control)            │
│                                 │   │         │                       │
│                                 │   │         ▼                       │
│                                 │   │  2x Speakers                    │
└─────────────────────────────────┘   └─────────────────────────────────┘
```

### Why DMX?

Serial communication is unstable over the required 10-15 meter cable distances. DMX provides reliable communication and allows a single signal to control both lighting and audio systems simultaneously.

### Communication Flow

1. LD2410C radar sensor detects human presence
2. Arduino reads sensor and handles debouncing
3. Arduino broadcasts DMX (channel 1: 0=absent, 1=present)
4. Lighting responds directly to DMX signal
5. Raspberry Pi receives DMX via Enttec USB Pro
6. Python script converts DMX to OSC message
7. RNBO triggers crossfade between soundscapes

## Hardware

### Audio System (Raspberry Pi)

| Component | Description |
|-----------|-------------|
| Raspberry Pi 5 | Main audio processor |
| HiFiBerry DAC8x | 8-channel audio output (steel case) |
| Enttec DMX USB Pro | DMX-to-USB interface |
| 2x Speakers | Mounted above installation |

### Presence Detection (Arduino)

| Component | Description |
|-----------|-------------|
| Arduino | Master controller |
| DMX Shield | Outputs DMX signal |
| Hi-Link LD2410C | 5V Microwave Radar (detects stationary + moving people) |

### Lighting

| Component | Description |
|-----------|-------------|
| Custom LED Light Bars | Color-changing LED strings |
| 2x Gobo Projectors | "Water lamps" with built-in patterns |

### Physical Installation

| Element | Specification |
|---------|---------------|
| Fabric | Liquid organza cylinder, ~150cm width × 300cm height |
| Height | Suspended ~3 meters above ground |
| Environment | Outdoor, temperatures down to -5°C |

## File Structure

```
├── README.md                    # This file
├── presence_sensor.py           # DMX-to-OSC bridge (runs on Pi)
├── test_dmx.py                  # Test script for DMX reception
├── test_osc.py                  # Test script for OSC to RNBO
├── dmx-osc-bridge.service       # Systemd service file
├── SYSTEMD_SERVICE.md           # Service documentation
└── rnbo/                        # RNBO patch files (Max/MSP)
```

### Script Descriptions

| File | Purpose |
|------|---------|
| `presence_sensor.py` | Main script. Reads DMX from Enttec, sends OSC to RNBO |
| `test_dmx.py` | Verifies Enttec connection and DMX reception |
| `test_osc.py` | Verifies OSC communication with RNBO |
| `dmx-osc-bridge.service` | Systemd service for auto-start at boot |

## Raspberry Pi Setup

### Step 1: Flash RNBO Image

The Raspberry Pi runs Cycling74's custom RNBO image.

**Requirements:**
- Raspberry Pi 5 (also supports Pi 3, Pi 4, Pi Zero 2 W)
- SD Card (16GB+ recommended)
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)

**Flashing with Raspberry Pi Imager:**

1. Open Raspberry Pi Imager
2. Click **APP OPTIONS** (lower left)
3. Click **EDIT** next to Content Repository
4. Select **Use custom URL** and enter:
   ```
   http://assets.cycling74.com/rnbo/pi-images/repo.json
   ```
5. Click **APPLY & RESTART**
6. Select your device and the RNBO image
7. Configure settings:
   - Set hostname (e.g., `c74rpi`)
   - Keep username as `pi` (required!)
   - Set password
   - Configure WiFi if needed
   - Enable SSH under Remote Access
8. Click **WRITE**

**Default credentials:**
- Username: `pi`
- Password: `c74rnbo` (unless changed during flashing)

For detailed instructions, see: https://rnbo.cycling74.com/learn/raspberry-pi-setup

### Step 2: Connect via SSH

```bash
ssh pi@c74rpi.local
```

### Step 3: Install Python Dependencies

```bash
pip install pyserial python-osc requests --break-system-packages
```

### Step 4: Copy Scripts to Pi

From your computer:
```bash
scp presence_sensor.py pi@c74rpi.local:/home/pi/
scp test_dmx.py pi@c74rpi.local:/home/pi/
scp test_osc.py pi@c74rpi.local:/home/pi/
scp SYSTEMD_SERVICE.md pi@c74rpi.local:/home/pi/
```

### Step 5: Install Systemd Service

On the Pi:
```bash
sudo nano /etc/systemd/system/dmx-osc-bridge.service
```

Paste this content:
```ini
[Unit]
Description=DMX to OSC Bridge for Purple Rain Installation
After=rnbooscquery.service network-online.target
Wants=network-online.target rnbooscquery.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi
ExecStartPre=/bin/sleep 10
ExecStart=/usr/bin/python3 /home/pi/presence_sensor.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=dmx-osc-bridge

[Install]
WantedBy=multi-user.target
```

Save with `Ctrl+X`, `Y`, `Enter`.

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dmx-osc-bridge.service
sudo systemctl start dmx-osc-bridge.service
```

### Step 6: Export RNBO Patch

1. Open your RNBO patch in Max/MSP
2. The Pi should appear under **Devices** in the Export Sidebar
3. Double-click to configure and export

## DMX Protocol

| Parameter | Value |
|-----------|-------|
| Universe | 1 |
| Channel | 1 |
| Absent value | 0 |
| Present value | 1 |

The Arduino handles debouncing to ensure synchronized light and sound response.

## Testing

### Test DMX Reception

Connect Enttec DMX USB Pro and run:
```bash
python3 test_dmx.py
```

Expected output shows channel 1 values when Arduino sends DMX.

### Test OSC to RNBO

With RNBO patch running:
```bash
python3 test_osc.py
```

This sends fadeTrig=1, waits 3 seconds, then sends fadeTrig=0.

### Verify Enttec Connection

```bash
ls /dev/ttyUSB*
```

Should show `/dev/ttyUSB0` when Enttec is connected.

## Useful Commands

### Service Management

| Command | Description |
|---------|-------------|
| `sudo systemctl status dmx-osc-bridge` | Check status |
| `sudo systemctl start dmx-osc-bridge` | Start service |
| `sudo systemctl stop dmx-osc-bridge` | Stop service |
| `sudo systemctl restart dmx-osc-bridge` | Restart service |

### Viewing Logs

| Command | Description |
|---------|-------------|
| `journalctl -u dmx-osc-bridge -f` | Live log |
| `journalctl -u dmx-osc-bridge -n 50` | Last 50 lines |
| `journalctl -u dmx-osc-bridge --since "1 hour ago"` | Last hour |

### System

| Command | Description |
|---------|-------------|
| `sudo reboot` | Reboot Pi |
| `sudo shutdown -h now` | Shutdown Pi |
| `sudo systemctl status rnbooscquery` | Check RNBO status |

## Troubleshooting

### Enttec not detected

```bash
ls /dev/ttyUSB*
```

If no output, check USB connection. If permission denied:
```bash
sudo chmod 666 /dev/ttyUSB0
```

### Service keeps restarting

Check logs for errors:
```bash
journalctl -u dmx-osc-bridge -n 30
```

Common causes:
- Enttec not connected
- RNBO not running
- Wrong serial port

### RNBO not responding

Verify RNBO is running:
```bash
sudo systemctl status rnbooscquery
```

Check OSCQuery is accessible:
```bash
curl http://localhost:5678
```

### Pi not appearing in Max/MSP

- Ensure Pi and computer are on same network
- Wait a few minutes after boot
- Try connecting via ethernet
- Verify hostname with `hostname` command on Pi

## Technical Notes

### Thermal Management

The Pi 5 generates sufficient self-heating (18-20°C above ambient) to prevent condensation in cold outdoor conditions down to -5°C. The HiFiBerry steel case provides additional protection.

### Audio Looping in RNBO

- Uses dual `groove~' objects: One for each loop
- Handles reverb tails using Abletons "Render as loop" functionality
- Requires explicit `bang` to initiate playback (unlike standard Max)

### Network Configuration

If both WiFi and ethernet are connected on the same subnet, routing issues may occur. Use `sudo nmtui` to configure network settings.

## Resources

### Cycling74 / RNBO

- [RNBO Raspberry Pi Overview](https://rnbo.cycling74.com/learn/raspberry-pi-target-overview)
- [Raspberry Pi Setup Guide](https://rnbo.cycling74.com/learn/raspberry-pi-setup)
- [Configuring Audio](https://rnbo.cycling74.com/learn/configuring-audio-on-the-raspberry-pi)
- [Web Interface Guide](https://rnbo.cycling74.com/learn/raspberry-pi-web-interface-guide)
- [FAQ and Troubleshooting](https://rnbo.cycling74.com/learn/working-with-the-raspberry-pi-target)

### Hardware

- [HiFiBerry DAC8x](https://www.hifiberry.com/shop/boards/hifiberry-dac8x/)
- [Enttec DMX USB Pro](https://www.enttec.com/product/dmx-usb-interfaces/dmx-usb-pro/)
- [Hi-Link LD2410C Radar](https://www.hlktech.net/index.php?id=1095)

## License

[Specify license]

## Authors

Copenhagen Light Festival Installation Team
