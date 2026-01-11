#!/usr/bin/env python3
"""
DMX to RNBO OSC Bridge
----------------------
Receives DMX signal from Enttec DMX USB Pro and sends presence state to RNBO
via OSC to trigger crossfade between dystopian and utopian soundscapes.

System architecture:
- Arduino + DMX Shield reads LD2410C presence sensor and broadcasts DMX
- This script receives DMX channel 1 (0=absent, 1=present) via Enttec USB Pro
- Sends OSC to RNBO to trigger audio crossfade

Hardware:
- Raspberry Pi 5 with HiFiBerry DAC8x
- Enttec DMX USB Pro (receives DMX from Arduino)

Dependencies:
- pip install pyserial python-osc requests --break-system-packages

Author: Copenhagen Light Festival Installation
"""

import time
import socket
import logging
import serial
from typing import Optional

import requests
from pythonosc.udp_client import SimpleUDPClient

# ----- Configuration -----
# Serial port for Enttec DMX USB Pro
# 
# To find the correct port, run in terminal:
#   ls /dev/ttyUSB*
# 
# Typical values:
#   - /dev/ttyUSB0  (most common, first USB-serial device)
#   - /dev/ttyUSB1  (if another USB-serial device is connected)
#
# For more detailed info about connected devices:
#   python -c "import serial.tools.list_ports; [print(p.device, p.description) for p in serial.tools.list_ports.comports()]"
#
# The Enttec will show as "FT232R USB UART" or similar FTDI device
DMX_SERIAL_PORT = "/dev/ttyUSB0"

# OSC Configuration - RNBO runner listens on port 1234
OSC_PORT = 1234

# OSCQuery HTTP port for discovering RNBO parameters
OSCQUERY_PORT = 5678

# RNBO parameter path for fade trigger
# fadeTrig: 0 = dystopian (no presence), 1 = utopian (presence detected)
PRESENCE_PARAM_PATH = "/rnbo/inst/0/params/fadeTrig"

# DMX channel to read for presence (1-indexed as per DMX convention)
DMX_PRESENCE_CHANNEL = 1

# Polling interval in seconds
POLL_INTERVAL = 0.05  # 50ms - fast enough to catch DMX updates

# ----- Enttec DMX USB Pro Protocol Constants -----
ENTTEC_START_DELIMITER = 0x7E
ENTTEC_END_DELIMITER = 0xE7
ENTTEC_LABEL_DMX_RECEIVED = 5

# ----- Logging Setup -----
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RNBOConnection:
    """
    Handles OSCQuery discovery and OSC communication with RNBO runner.
    """
    
    def __init__(self, osc_port: int = OSC_PORT, oscquery_port: int = OSCQUERY_PORT):
        self.osc_port = osc_port
        self.oscquery_port = oscquery_port
        self.osc_client: Optional[SimpleUDPClient] = None
        self.ip_address: Optional[str] = None
        self.oscquery_url: Optional[str] = None
        
    def discover(self) -> bool:
        """
        Discover RNBO runner via OSCQuery. Resolves hostname and verifies connection.
        Returns True if successful, False otherwise.
        """
        # Resolve hostname to IP address
        hostname = socket.gethostname() + ".local"
        try:
            self.ip_address = socket.gethostbyname(hostname)
            logger.info(f"Resolved hostname '{hostname}' to IP: {self.ip_address}")
        except socket.gaierror:
            # Fallback to localhost
            self.ip_address = "127.0.0.1"
            logger.warning("Could not resolve hostname, using localhost")
            
        self.oscquery_url = f"http://{self.ip_address}:{self.oscquery_port}"
        
        # Verify OSCQuery is responding
        try:
            response = requests.get(self.oscquery_url, timeout=2)
            if response.status_code == 200:
                logger.info(f"OSCQuery server found at {self.oscquery_url}")
                self.osc_client = SimpleUDPClient(self.ip_address, self.osc_port)
                return True
            else:
                logger.error(f"OSCQuery returned status {response.status_code}")
                return False
        except requests.RequestException as e:
            logger.error(f"Could not connect to OSCQuery: {e}")
            return False
            
    def fetch_tree(self) -> Optional[dict]:
        """Fetch full OSCQuery tree to inspect available parameters."""
        if not self.oscquery_url:
            return None
        try:
            response = requests.get(self.oscquery_url, timeout=2)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching OSCQuery tree: {e}")
        return None
    
    def find_parameter_path(self, search_paths: list) -> Optional[str]:
        """
        Search OSCQuery tree for any of the given parameter paths.
        Returns the first found path or None.
        """
        tree = self.fetch_tree()
        if not tree:
            return None
            
        for path in search_paths:
            if self._search_tree(tree, path) is not None:
                logger.info(f"Found parameter path: {path}")
                return path
        return None
        
    def _search_tree(self, tree: dict, target_path: str):
        """Recursively search OSCQuery tree for a specific path."""
        if not isinstance(tree, dict):
            return None
        if tree.get("FULL_PATH") == target_path:
            val = tree.get("value") or tree.get("VALUE")
            return val[0] if isinstance(val, list) and val else val
        for child in (tree.get("CONTENTS") or {}).values():
            result = self._search_tree(child, target_path)
            if result is not None:
                return result
        return None
        
    def send_presence(self, value: int, path: str = PRESENCE_PARAM_PATH):
        """
        Send fade trigger value to RNBO via OSC.
        
        Args:
            value: 0 (no presence/dystopian) or 1 (presence/utopian)
            path: OSC address path for the fadeTrig parameter
        """
        if self.osc_client:
            self.osc_client.send_message(path, value)
            logger.debug(f"Sent OSC: {path} = {value}")


class EnttecDMXReceiver:
    """
    Receives DMX data from Enttec DMX USB Pro.
    
    Protocol based on Enttec DMX USB Pro API v1.44:
    - Message format: [0x7E][Label][LengthLSB][LengthMSB][Data...][0xE7]
    - Label 5 = Received DMX Packet
    - First data byte = status (0 = valid)
    - Remaining bytes = DMX values starting with start code (byte 0)
    - DMX channel 1 is at data index 2 (after status byte and start code)
    """
    
    def __init__(self, port: str = DMX_SERIAL_PORT):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.dmx_data = [0] * 513  # Start code + 512 channels
        
    def connect(self) -> bool:
        """
        Open serial connection to Enttec DMX USB Pro.
        Returns True if successful.
        """
        try:
            # Enttec uses virtual COM port - baudrate is ignored but required
            self.serial = serial.Serial(
                port=self.port,
                baudrate=57600,  # Dummy value, USB handles actual speed
                timeout=1.0
            )
            logger.info(f"Connected to Enttec DMX USB Pro on {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to Enttec: {e}")
            return False
    
    def _read_message(self) -> Optional[tuple]:
        """
        Read and parse one Enttec message from serial.
        
        Returns:
            Tuple of (label, data) if valid message, None otherwise
        """
        if not self.serial:
            return None
            
        # Find start delimiter
        while True:
            byte = self.serial.read(1)
            if not byte:
                return None  # Timeout
            if byte[0] == ENTTEC_START_DELIMITER:
                break
        
        # Read label and length
        header = self.serial.read(3)
        if len(header) < 3:
            return None
            
        label = header[0]
        length = header[1] | (header[2] << 8)
        
        # Read data
        data = self.serial.read(length) if length > 0 else b''
        if len(data) < length:
            return None
            
        # Read end delimiter
        end = self.serial.read(1)
        if not end or end[0] != ENTTEC_END_DELIMITER:
            logger.warning("Invalid end delimiter")
            return None
            
        return (label, data)
    
    def read_dmx_channel(self, channel: int) -> Optional[int]:
        """
        Read a specific DMX channel value.
        
        Args:
            channel: DMX channel number (1-512)
            
        Returns:
            Channel value (0-255) or None if no valid data
        """
        message = self._read_message()
        if not message:
            return None
            
        label, data = message
        
        # Only process DMX received packets (label 5)
        if label != ENTTEC_LABEL_DMX_RECEIVED:
            return None
            
        # First byte is status (0 = valid)
        if len(data) < 2 or data[0] != 0:
            return None
            
        # Data format: [status][start_code][ch1][ch2]...[ch512]
        # Channel 1 is at index 2 (after status and start code)
        dmx_index = channel + 1  # +1 for start code (status already at index 0)
        
        if dmx_index >= len(data):
            return None
            
        return data[dmx_index]
    
    def get_presence(self) -> Optional[bool]:
        """
        Read presence state from DMX channel.
        
        Returns:
            True if presence detected (DMX > 0), False if absent, None if no data
        """
        value = self.read_dmx_channel(DMX_PRESENCE_CHANNEL)
        if value is None:
            return None
        return value > 0
    
    def close(self):
        """Close serial connection."""
        if self.serial:
            self.serial.close()
            logger.info("Enttec connection closed")


class DMXToOSCBridge:
    """
    Main application class that bridges DMX presence signal to RNBO OSC.
    """
    
    def __init__(self):
        self.rnbo = RNBOConnection()
        self.dmx = EnttecDMXReceiver()
        self.running = False
        self.current_presence = False
        self.param_path = PRESENCE_PARAM_PATH
        
    def setup(self) -> bool:
        """
        Initialize all components.
        Returns True if setup successful.
        """
        # Discover RNBO
        logger.info("Searching for RNBO runner...")
        max_retries = 30
        retry_count = 0
        
        while retry_count < max_retries:
            if self.rnbo.discover():
                break
            retry_count += 1
            logger.info(f"Retry {retry_count}/{max_retries}...")
            time.sleep(1)
        else:
            logger.error("Could not find RNBO runner after max retries")
            return False
            
        # Try to find the fadeTrig parameter in RNBO
        possible_paths = [
            "/rnbo/inst/0/params/fadeTrig",
            "/rnbo/inst/1/params/fadeTrig",
        ]
        
        found_path = self.rnbo.find_parameter_path(possible_paths)
        if found_path:
            self.param_path = found_path
        else:
            logger.warning(f"Parameter not found in OSCQuery, using default: {self.param_path}")
            
        # Connect to Enttec DMX USB Pro
        logger.info("Connecting to Enttec DMX USB Pro...")
        if not self.dmx.connect():
            logger.error("Could not connect to Enttec DMX USB Pro")
            return False
            
        logger.info("Setup complete!")
        return True
        
    def run(self):
        """
        Main loop - reads DMX and sends OSC messages.
        """
        self.running = True
        logger.info(f"Starting main loop, reading DMX ch{DMX_PRESENCE_CHANNEL}, sending to {self.param_path}")
        
        try:
            while self.running:
                # Read presence from DMX
                presence = self.dmx.get_presence()
                
                if presence is not None and presence != self.current_presence:
                    self.current_presence = presence
                    state_str = "PRESENT (utopian)" if presence else "ABSENT (dystopian)"
                    logger.info(f"Presence changed: {state_str}")
                
                # Send current state to RNBO (send every cycle to ensure sync)
                fade_value = 1 if self.current_presence else 0
                self.rnbo.send_presence(fade_value, self.param_path)
                
                time.sleep(POLL_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.shutdown()
            
    def shutdown(self):
        """Clean shutdown of all components."""
        self.running = False
        self.dmx.close()
        logger.info("Shutdown complete")


def main():
    """Entry point for the DMX to OSC bridge."""
    logger.info("=" * 50)
    logger.info("Copenhagen Light Festival - DMX to OSC Bridge")
    logger.info("=" * 50)
    
    bridge = DMXToOSCBridge()
    
    if bridge.setup():
        bridge.run()
    else:
        logger.error("Setup failed, exiting")
        return 1
        
    return 0


if __name__ == "__main__":
    exit(main())