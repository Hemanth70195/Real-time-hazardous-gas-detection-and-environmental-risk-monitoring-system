# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Mock ESP32 Serial Telemetry Sender & Feeder (Phase 5).
Utility script to test live telemetry streaming before physical ESP32 hardware is connected.
Integrates MockESP32TelemetryGenerator to simulate realistic scenarios.

Usage Options:
1. Software direct-feed testing (no virtual COM port needed):
   python tools/mock_esp32_feeder.py --mode direct --scenario normal --interval 2.0 --count 10

2. Virtual COM Port pair testing (requires virtual COM pair, e.g. COM10 <-> COM11):
   python tools/mock_esp32_feeder.py --mode serial --port COM11 --baud 115200 --interval 2.0 --scenario gas-spike
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mock_esp32_generator import MockESP32TelemetryGenerator


def get_scenario_payload(generator: MockESP32TelemetryGenerator, scenario: str):
    """Retrieves payload based on selected scenario."""
    if scenario == "normal":
        return generator.generate_normal()
    elif scenario == "high-temp":
        return generator.generate_high_temperature(38.5)
    elif scenario == "low-hum":
        return generator.generate_low_humidity(18.0)
    elif scenario == "high-hum":
        return generator.generate_high_humidity(88.0)
    elif scenario == "gas-spike":
        return generator.generate_gas_spike(3400)
    elif scenario == "noise-spike":
        return generator.generate_noise_spike(3600)
    elif scenario == "missing-sensors":
        return generator.generate_missing_sensors(missing_temp=True, missing_gas=True)
    elif scenario == "out-of-range":
        return generator.generate_out_of_range()
    elif scenario == "invalid-json":
        return generator.generate_invalid_json()
    else:
        return generator.generate_normal()


def run_virtual_serial_stream(port: str, baud_rate: int = 115200, interval: float = 2.0, scenario: str = "normal"):
    """Streams JSON lines to a real or virtual serial COM port."""
    try:
        import serial
    except ImportError:
        print("Error: pyserial is required for serial mode. Run: pip install pyserial")
        sys.exit(1)

    generator = MockESP32TelemetryGenerator()
    print(f"Opening serial port {port} at {baud_rate} baud...")
    try:
        ser = serial.Serial(port=port, baudrate=baud_rate, timeout=1.0)
    except Exception as e:
        print(f"Failed to open port {port}: {e}")
        print("Hint: To test over virtual serial ports, create a virtual pair using com0com or tty0tty.")
        sys.exit(1)

    print(f"Streaming mock ESP32 telemetry (scenario: {scenario}) to {port} every {interval}s (Ctrl+C to stop)...")
    try:
        pkt_num = 0
        while True:
            payload = get_scenario_payload(generator, scenario)
            line = generator.to_serial_line(payload)
            ser.write(line.encode("utf-8"))
            ser.flush()
            pkt_num += 1
            print(f"[{pkt_num:04d}] Transmitted: {line.strip()}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStreaming halted by user.")
    finally:
        ser.close()
        print("Port closed.")


def run_direct_feed_loop(interval: float = 2.0, count: int = 10, scenario: str = "normal"):
    """Feeds mock packets directly into the in-memory SerialSensorReceiver singleton."""
    from core.serial_sensor_receiver import get_serial_receiver
    receiver = get_serial_receiver()
    generator = MockESP32TelemetryGenerator()
    print(f"Feeding {count} packets (scenario: {scenario}) into SerialSensorReceiver every {interval}s...")

    for i in range(1, count + 1):
        payload = get_scenario_payload(generator, scenario)
        line = generator.to_serial_line(payload)
        parsed = receiver.process_incoming_line(line)
        status = receiver.get_status()
        scenario_tag = payload.get("_scenario", "RAW_STRING") if isinstance(payload, dict) else "INVALID_STRING"
        print(f"[{i:03d} - {scenario_tag}] Processed: {line.strip()}")
        print(f"      Valid={parsed is not None}, Pkts={status['messages_received']}, Errors={status['errors_count']}, Stale={status['is_stale']}")
        if i < count:
            time.sleep(interval)

    print("Direct feed test completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SafeEdge HazardGuard Mock ESP32 Telemetry Feeder")
    parser.add_argument("--mode", choices=["direct", "serial"], default="direct", help="Feed mode: direct in-memory or serial COM port")
    parser.add_argument("--port", default="COM11", help="Target serial COM port (for --mode serial)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--interval", type=float, default=2.0, help="Transmission interval in seconds (default: 2.0)")
    parser.add_argument("--count", type=int, default=10, help="Number of packets for direct mode (default: 10)")
    parser.add_argument(
        "--scenario",
        choices=["normal", "high-temp", "low-hum", "high-hum", "gas-spike", "noise-spike", "missing-sensors", "out-of-range", "invalid-json"],
        default="normal",
        help="Telemetry simulation scenario",
    )
    args = parser.parse_args()

    if args.mode == "direct":
        run_direct_feed_loop(interval=args.interval, count=args.count, scenario=args.scenario)
    else:
        run_virtual_serial_stream(port=args.port, baud_rate=args.baud, interval=args.interval, scenario=args.scenario)
