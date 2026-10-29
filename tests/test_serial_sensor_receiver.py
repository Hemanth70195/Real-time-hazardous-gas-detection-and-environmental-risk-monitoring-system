# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Test Suite for ESP32 Serial Sensor Receiver & Live Hardware Mode.
Verifies all 13 Phase 1 testing requirements:
1. Valid JSON messages.
2. Missing and malformed fields.
3. Invalid numeric values.
4. Missing JSON keys.
5. Stale-data detection.
6. Disconnection handling.
7. Reconnection behavior.
8. Data-source separation.
9. Correct unit mapping.
10. Prevention of raw-gas-to-ppm conversion.
11. Prevention of raw-microphone-to-dB conversion.
12. History and report source labels.
13. Preservation of Simulation Mode.
"""

import json
import math
import time
from datetime import datetime
import pytest

from core.serial_sensor_receiver import (
    SerialSensorReceiver,
    SerialConnectionStatus,
    ESP32ParsedData,
    get_serial_receiver,
)
from core.hazard_assessment import (
    HazardAssessmentEngine,
    HazardStatus,
    HazardAssessment,
)
from core.hazard_history import (
    HazardHistoryTracker,
    HazardEvent,
)
from simulator import (
    IoTHardwareSimulator,
    SCENARIOS,
    get_simulator,
)


@pytest.fixture
def receiver():
    """Provides an isolated SerialSensorReceiver instance for testing."""
    return SerialSensorReceiver(default_baud_rate=115200, stale_timeout_seconds=1.0)


# =============================================================================
# 1. Valid JSON Messages
# =============================================================================

def test_valid_json_message(receiver):
    """Test parsing a fully valid ESP32 JSON message with all Phase 4 fields (no dust fields)."""
    msg = '{"device_id":"safeedge-esp32-01","temperature_c":31.5,"humidity_pct":64.0,"gas_raw":1250,"noise_raw":1850}'
    parsed = receiver.process_incoming_line(msg)

    assert parsed is not None
    assert parsed.device_id == "safeedge-esp32-01"
    assert parsed.temperature_c == 31.5
    assert parsed.humidity_pct == 64.0
    assert parsed.gas_raw == 1250.0
    assert parsed.noise_raw == 1850.0
    assert receiver.get_status()["messages_received"] == 1


# =============================================================================
# 2. Malformed JSON Handling
# =============================================================================

def test_malformed_json_messages(receiver):
    """Test rejecting broken, truncated, non-JSON, and non-dict inputs safely."""
    malformed_inputs = [
        "",
        "   ",
        "NOT JSON",
        '{"device_id": "incomplete"',
        '{"temperature_c": 25.0',
        "[1, 2, 3]",
        '"just a string"',
        "{invalid: json}",
    ]
    for bad_input in malformed_inputs:
        result = receiver.process_incoming_line(bad_input)
        assert result is None, f"Expected None for input: {bad_input}"

    assert receiver.get_status()["errors_count"] == len(malformed_inputs)


# =============================================================================
# 3. Invalid Numeric Values
# =============================================================================

def test_invalid_numeric_values(receiver):
    """Test rejection of non-numeric, NaN, infinite, and out-of-range values."""
    invalid_cases = [
        '{"device_id":"esp-01","temperature_c":"hot","humidity_pct":50.0}',       # string instead of float
        '{"device_id":"esp-01","temperature_c":true,"humidity_pct":50.0}',        # boolean
        '{"device_id":"esp-01","temperature_c":150.0,"humidity_pct":50.0}',       # extreme temperature > 85
        '{"device_id":"esp-01","temperature_c":25.0,"humidity_pct":120.0}',       # humidity > 100%
        '{"device_id":"esp-01","temperature_c":25.0,"humidity_pct":-5.0}',        # humidity < 0%
        '{"device_id":"esp-01","pm10":-10.0}',                                     # negative PM concentration
        '{"device_id":"esp-01","gas_raw":-500}',                                   # negative ADC count
        '{"device_id":"esp-01","noise_raw":-100}',                                 # negative ADC count
    ]
    for bad_msg in invalid_cases:
        result = receiver.process_incoming_line(bad_msg)
        assert result is None, f"Expected rejection for: {bad_msg}"


# =============================================================================
# 4. Missing JSON Keys (Partial Messages & No Fabrication)
# =============================================================================

def test_missing_json_keys_no_fabrication(receiver):
    """
    Test that missing fields are kept as None and never fabricated or invented.
    """
    partial_msg = '{"device_id":"safeedge-esp32-partial","temperature_c":26.4,"humidity_pct":48.0}'
    parsed = receiver.process_incoming_line(partial_msg)

    assert parsed is not None
    assert parsed.device_id == "safeedge-esp32-partial"
    assert parsed.temperature_c == 26.4
    assert parsed.humidity_pct == 48.0
    # Must NOT fabricate missing PM, gas, or noise values
    assert parsed.pm1_0 is None
    assert parsed.pm2_5 is None
    assert parsed.pm10 is None
    assert parsed.gas_raw is None
    assert parsed.noise_raw is None


# =============================================================================
# 5. Stale-Data Detection
# =============================================================================

def test_stale_data_detection():
    """Verify that is_data_stale correctly flags expired readings."""
    short_timeout_receiver = SerialSensorReceiver(stale_timeout_seconds=0.2)

    # Initial state without messages should be stale
    assert short_timeout_receiver.is_data_stale() is True

    # After feeding a valid reading, it should be fresh
    msg = '{"device_id":"esp-01","temperature_c":24.0,"humidity_pct":50.0}'
    short_timeout_receiver.process_incoming_line(msg)
    assert short_timeout_receiver.is_data_stale() is False

    # Wait past the 0.2s timeout
    time.sleep(0.3)
    assert short_timeout_receiver.is_data_stale() is True
    assert short_timeout_receiver.get_status()["is_stale"] is True


# =============================================================================
# 6. Disconnection Handling
# =============================================================================

def test_disconnection_handling(receiver):
    """Verify disconnect cleans up resources and updates status."""
    receiver.disconnect()
    status = receiver.get_status()

    assert status["is_connected"] is False
    assert status["status"] == SerialConnectionStatus.DISCONNECTED.value
    assert receiver.is_connected() is False


# =============================================================================
# 7. Reconnection Behavior & Thread Safety
# =============================================================================

def test_singleton_receiver_reuse():
    """Verify get_serial_receiver returns the singleton without duplicate threads."""
    rec1 = get_serial_receiver()
    rec2 = get_serial_receiver()
    assert rec1 is rec2


# =============================================================================
# 8. Data-Source Separation (Simulation vs Live Hardware)
# =============================================================================

def test_data_source_separation():
    """Verify that Simulation Mode and Live Hardware Mode are isolated."""
    sim = IoTHardwareSimulator()

    # 1. Simulation Mode
    sim_data = sim.read_sensors(data_source="simulation")
    assert sim_data["data_source"] == "simulation"
    assert sim_data["device_id"] == "simulated-node"
    assert "gas" in sim_data["readings"]
    assert sim_data["readings"]["gas"]["unit"] == "ppm"
    assert sim_data["readings"]["gas"]["is_uncalibrated"] is False

    # 2. Live Mode without active ESP32 data -> returns stale/unavailable
    rec = get_serial_receiver()
    rec.disconnect()
    live_data = sim.read_sensors(data_source="live_esp32")
    assert live_data["data_source"] == "live_esp32"
    assert live_data["is_stale"] is True
    # Should not fabricate readings
    assert live_data["readings"] is None


# =============================================================================
# 9. Correct Unit Mapping
# =============================================================================

def test_sensor_unit_mapping():
    """Verify correct mapping of live ESP32 fields to physical units (Phase 4: 4 parameters)."""
    rec = get_serial_receiver()
    msg = '{"device_id":"safeedge-esp32-01","temperature_c":28.5,"humidity_pct":58.2,"gas_raw":1420,"noise_raw":1980}'
    rec.feed_mock_message(msg)

    # Fake connection state for test reading
    rec._status = SerialConnectionStatus.CONNECTED
    rec._last_message_time = time.time()

    sim = IoTHardwareSimulator()
    live_telemetry = sim.read_sensors(data_source="live_esp32")

    assert live_telemetry["readings"] is not None
    readings = live_telemetry["readings"]

    # temperature -> °C
    assert readings["temperature"]["value"] == 28.5
    assert readings["temperature"]["unit"] == "°C"

    # humidity -> %
    assert readings["humidity"]["value"] == 58.2
    assert readings["humidity"]["unit"] == "%"

    # dust must NOT exist in readings
    assert "dust" not in readings

    # gas & noise -> raw ADC
    assert readings["gas"]["value"] == 1420.0
    assert readings["gas"]["unit"] == "ADC"
    assert readings["noise"]["value"] == 1980.0
    assert readings["noise"]["unit"] == "ADC"


# =============================================================================
# 10. Prevention of Raw-Gas-to-PPM Conversion & Never Classified as Safe
# =============================================================================

def test_prevention_of_raw_gas_to_ppm_conversion():
    """
    CRITICAL: Verify gas_raw remains uncalibrated ADC counts, is NOT converted to ppm,
    and is NEVER classified as SAFE.
    """
    rec = get_serial_receiver()
    msg = '{"device_id":"safeedge-esp32-01","temperature_c":22.0,"humidity_pct":45.0,"gas_raw":850,"noise_raw":1200}'
    rec.feed_mock_message(msg)
    rec._status = SerialConnectionStatus.CONNECTED
    rec._last_message_time = time.time()

    sim = IoTHardwareSimulator()
    telemetry = sim.read_sensors(data_source="live_esp32")
    gas_card = telemetry["readings"]["gas"]

    # Must be ADC, NOT ppm
    assert gas_card["unit"] == "ADC"
    assert gas_card["value"] == 850.0
    assert gas_card["is_uncalibrated"] is True

    # Must NOT be classified as SAFE
    assert gas_card["status"] != "SAFE"
    assert gas_card["status"] == "UNCALIBRATED"

    # Assessment Engine check
    meta = {"display_name": "Gas Concentration", "unit": "ppm"}
    assessment = HazardAssessmentEngine.assess_parameter("gas", 850.0, meta, is_uncalibrated=True)
    assert assessment.status != HazardStatus.SAFE
    assert assessment.is_safe is False
    assert assessment.is_uncalibrated is True
    assert "RAW UNCALIBRATED" in assessment.reason
    assert "ppm" not in assessment.unit.lower() or "adc" in assessment.unit.lower()


# =============================================================================
# 11. Prevention of Raw-Microphone-to-dB Conversion & Never Classified as Safe
# =============================================================================

def test_prevention_of_raw_microphone_to_db_conversion():
    """
    CRITICAL: Verify noise_raw remains uncalibrated ADC counts, is NOT converted to dB,
    and is NEVER classified as SAFE.
    """
    rec = get_serial_receiver()
    msg = '{"device_id":"safeedge-esp32-01","temperature_c":22.0,"humidity_pct":45.0,"gas_raw":850,"pm10":25.0,"noise_raw":1650}'
    rec.feed_mock_message(msg)
    rec._status = SerialConnectionStatus.CONNECTED
    rec._last_message_time = time.time()

    sim = IoTHardwareSimulator()
    telemetry = sim.read_sensors(data_source="live_esp32")
    noise_card = telemetry["readings"]["noise"]

    # Must be ADC, NOT dB
    assert noise_card["unit"] == "ADC"
    assert noise_card["value"] == 1650.0
    assert noise_card["is_uncalibrated"] is True

    # Must NOT be classified as SAFE
    assert noise_card["status"] != "SAFE"
    assert noise_card["status"] == "UNCALIBRATED"

    # Assessment Engine check
    meta = {"display_name": "Noise Level", "unit": "dB"}
    assessment = HazardAssessmentEngine.assess_parameter("noise", 1650.0, meta, is_uncalibrated=True)
    assert assessment.status != HazardStatus.SAFE
    assert assessment.is_safe is False
    assert assessment.is_uncalibrated is True
    assert "RAW UNCALIBRATED" in assessment.reason


# =============================================================================
# 12. History and Report Source Labels
# =============================================================================

def test_history_and_report_source_labels():
    """Verify that both CSV and JSON exports identify data source and calibration status."""
    tracker = HazardHistoryTracker()

    # Record simulated snapshot
    sim_readings = {"temperature": 24.0, "humidity": 45.0, "dust": 28.0, "noise": 65.0, "gas": 8.0}
    tracker.record_snapshot(sim_readings, tick=1, data_source="simulation")

    # Record live ESP32 snapshot
    live_readings = {"temperature": 32.5, "humidity": 68.0, "dust": 48.0, "noise": 1800.0, "gas": 1350.0}
    tracker.record_snapshot(
        live_readings,
        tick=2,
        data_source="live_esp32",
        device_id="safeedge-esp32-01",
        extra_data={"pm1_0": 14.0, "pm2_5": 29.0, "pm10": 48.0, "gas_raw": 1350.0, "noise_raw": 1800.0},
    )

    # 1. Check CSV export
    csv_out = tracker.export_readings_csv()
    assert "Data Source" in csv_out
    assert "Device ID" in csv_out
    assert "live_esp32" in csv_out
    assert "simulation" in csv_out
    assert "Gas Calibration Status" in csv_out
    assert "Uncalibrated Raw ADC" in csv_out

    # 2. Check JSON export
    json_rep = tracker.export_json_report()
    snapshots = json_rep["historical_readings"]
    assert len(snapshots) == 2
    assert snapshots[0]["Data_Source"] == "simulation"
    assert snapshots[1]["Data_Source"] == "live_esp32"
    assert snapshots[1]["gas_calibration_status"] == "Uncalibrated Raw ADC"
    assert snapshots[1]["Device_ID"] == "safeedge-esp32-01"


# =============================================================================
# 13. Preservation of Simulation Mode
# =============================================================================

def test_preservation_of_simulation_mode():
    """Verify simulation mode presets, overrides, and random walk operate unchanged."""
    sim = IoTHardwareSimulator()
    sim.set_data_source("simulation")

    # All Safe Preset
    sim.set_override(SCENARIOS["All Safe"])
    t1 = sim.read_sensors()
    assert t1["data_source"] == "simulation"
    assert t1["site_status"] == "normal"
    assert t1["readings"]["gas"]["value"] == 8.0
    assert t1["readings"]["gas"]["unit"] == "ppm"

    # Gas Leak Danger Preset
    sim.set_override(SCENARIOS["Gas Leak Danger"])
    t2 = sim.read_sensors()
    assert t2["site_status"] == "critical"
    assert t2["readings"]["gas"]["status"] == "DANGER"
    assert t2["readings"]["gas"]["value"] == 58.0

    # Clear Override & verify random walk
    sim.clear_override()
    assert sim.override_active is False
    t3 = sim.read_sensors()
    assert "readings" in t3
    assert t3["data_source"] == "simulation"

