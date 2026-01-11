#!/usr/bin/env python3
"""
Test script for Enttec DMX USB Pro reception.

Reads DMX channel 1 and prints the value to verify that:
1. Enttec DMX USB Pro is connected correctly
2. DMX signal is being received from Arduino
3. Presence values (0/1) are coming through

Usage:
    python test_dmx.py

To find the correct serial port first:
    ls /dev/ttyUSB*

Dependencies:
    pip install pyserial --break-system-packages
"""

import serial
import sys

# ----- Configuration -----
# Change this if your Enttec is on a different port
DMX_SERIAL_PORT = "/dev/ttyUSB0"
DMX_CHANNEL_TO_READ = 1

# Enttec protocol constants
ENTTEC_START_DELIMITER = 0x7E
ENTTEC_END_DELIMITER = 0xE7
ENTTEC_LABEL_DMX_RECEIVED = 5


def find_enttec_port():
    """List available serial ports to help find Enttec."""
    import serial.tools.list_ports
    
    print("Available serial ports:")
    print("-" * 40)
    
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("  No serial ports found!")
        return None
    
    for port in ports:
        print(f"  {port.device}")
        print(f"    Description: {port.description}")
        print(f"    Manufacturer: {port.manufacturer}")
        print()
    
    return ports


def read_dmx_message(ser):
    """
    Read one DMX message from Enttec.
    
    Returns:
        Tuple of (label, data) if valid, None otherwise
    """
    # Find start delimiter
    while True:
        byte = ser.read(1)
        if not byte:
            return None  # Timeout
        if byte[0] == ENTTEC_START_DELIMITER:
            break
    
    # Read label and length
    header = ser.read(3)
    if len(header) < 3:
        return None
    
    label = header[0]
    length = header[1] | (header[2] << 8)
    
    # Read data
    data = ser.read(length) if length > 0 else b''
    if len(data) < length:
        return None
    
    # Read end delimiter
    end = ser.read(1)
    if not end or end[0] != ENTTEC_END_DELIMITER:
        return None
    
    return (label, data)


def main():
    print("=" * 50)
    print("Enttec DMX USB Pro - Test Script")
    print("=" * 50)
    print()
    
    # Show available ports
    find_enttec_port()
    
    print(f"Attempting to connect to: {DMX_SERIAL_PORT}")
    print(f"Reading DMX channel: {DMX_CHANNEL_TO_READ}")
    print()
    
    try:
        ser = serial.Serial(
            port=DMX_SERIAL_PORT,
            baudrate=57600,  # Dummy value for Enttec
            timeout=2.0
        )
        print(f"Connected to {DMX_SERIAL_PORT}")
        print()
        print("Waiting for DMX data... (press Ctrl+C to stop)")
        print("-" * 50)
        
    except serial.SerialException as e:
        print(f"ERROR: Could not connect to {DMX_SERIAL_PORT}")
        print(f"       {e}")
        print()
        print("Tips:")
        print("  - Check that Enttec is plugged in")
        print("  - Try a different port from the list above")
        print("  - Check permissions: sudo chmod 666 /dev/ttyUSB0")
        return 1
    
    last_value = None
    message_count = 0
    
    try:
        while True:
            message = read_dmx_message(ser)
            
            if message is None:
                continue
            
            label, data = message
            
            # Only process DMX received packets (label 5)
            if label != ENTTEC_LABEL_DMX_RECEIVED:
                continue
            
            message_count += 1
            
            # Check status byte (first byte, 0 = valid)
            if len(data) < 2:
                print(f"[{message_count}] Invalid: data too short")
                continue
                
            status = data[0]
            if status != 0:
                print(f"[{message_count}] Invalid: status byte = {status}")
                continue
            
            # Get channel value
            # Data format: [status][start_code][ch1][ch2]...
            # Channel 1 is at index 2
            channel_index = DMX_CHANNEL_TO_READ + 1  # +1 for start code
            
            if channel_index >= len(data):
                print(f"[{message_count}] Channel {DMX_CHANNEL_TO_READ} not in data (only {len(data)-2} channels)")
                continue
            
            value = data[channel_index]
            
            # Only print when value changes (to reduce spam)
            if value != last_value:
                presence_str = "PRESENT" if value > 0 else "ABSENT"
                print(f"[{message_count}] Channel {DMX_CHANNEL_TO_READ} = {value} ({presence_str})")
                last_value = value
                
    except KeyboardInterrupt:
        print()
        print("-" * 50)
        print(f"Stopped. Total messages received: {message_count}")
        
    finally:
        ser.close()
        print("Connection closed.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())