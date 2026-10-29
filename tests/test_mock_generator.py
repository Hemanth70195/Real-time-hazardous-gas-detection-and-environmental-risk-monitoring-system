# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Test Suite for Mock ESP32 Telemetry Generator (Phase 5).
Verifies all generation scenarios required for hardware-independent system testing.
"""

import json
import pytest
from tools.mock_esp32_generator import MockESP32TelemetryGenerator


@pytest.fixture
def generator():
    return MockESP32TelemetryGenerator(device_id="test-esp32-node")


def test_generate_normal_schema(generator):
    """Verify normal telemetry contains required Phase 4 fields and no dust."""
    pkt = generator.generate_normal()
    assert pkt["device_id"] == "test-esp32-node"
    assert 21.0 <= pkt["temperature_c"] <= 26.0
    assert 45.0 <= pkt["humidity_pct"] <= 55.0
    assert 0 <= pkt["gas_raw"] <= 4095
    assert 0 <= pkt["noise_raw"] <= 4095
    assert pkt["uptime_ms"] > 0
    assert "pm1_0" not in pkt
    assert "pm2_5" not in pkt
    assert "pm10" not in pkt
    assert pkt["_simulated_test_data"] is True


def test_generate_high_temperature(generator):
    """Verify high temperature anomaly scenario."""
    pkt = generator.generate_high_temperature(40.2)
    assert pkt["temperature_c"] == 40.2
    assert pkt["_scenario"] == "HIGH_TEMPERATURE"


def test_generate_low_and_high_humidity(generator):
    """Verify humidity anomaly scenarios."""
    low = generator.generate_low_humidity(15.0)
    assert low["humidity_pct"] == 15.0

    high = generator.generate_high_humidity(92.0)
    assert high["humidity_pct"] == 92.0


def test_generate_gas_and_noise_spikes(generator):
    """Verify raw ADC spike scenarios."""
    gas = generator.generate_gas_spike(3800)
    assert gas["gas_raw"] == 3800

    noise = generator.generate_noise_spike(3750)
    assert noise["noise_raw"] == 3750


def test_generate_missing_sensors(generator):
    """Verify partial sensor failure scenarios."""
    partial = generator.generate_missing_sensors(missing_temp=True, missing_gas=True)
    assert partial["temperature_c"] is None
    assert partial["gas_raw"] is None
    assert partial["humidity_pct"] is not None
    assert partial["noise_raw"] is not None

    all_fail = generator.generate_all_sensors_disconnected()
    assert all_fail["temperature_c"] is None
    assert all_fail["humidity_pct"] is None
    assert all_fail["gas_raw"] is None
    assert all_fail["noise_raw"] is None


def test_generate_invalid_json(generator):
    """Verify invalid JSON strings cannot be parsed by standard json.loads."""
    for _ in range(10):
        bad_json = generator.generate_invalid_json()
        assert isinstance(bad_json, str)
        with pytest.raises(Exception):
            json.loads(bad_json)


def test_generate_malformed_messages(generator):
    """Verify malformed messages miss required keys or contain bad types."""
    for _ in range(10):
        malformed = generator.generate_malformed_message()
        assert isinstance(malformed, dict)
        # Check that it either misses fields or has wrong types
        is_malformed = (
            "device_id" not in malformed
            or not isinstance(malformed["device_id"], str)
            or malformed.get("device_id") == ""
            or not isinstance(malformed.get("temperature_c", 0.0), (int, float, type(None)))
            or not isinstance(malformed.get("humidity_pct", 0.0), (int, float, type(None)))
            or not isinstance(malformed.get("gas_raw", 0), (int, float, type(None)))
        )
        assert is_malformed


def test_generate_out_of_range(generator):
    """Verify out-of-range scenarios violate physical or ADC bounds."""
    for _ in range(10):
        oor = generator.generate_out_of_range()
        is_out = (
            oor["temperature_c"] > 85.0
            or oor["temperature_c"] < -40.0
            or oor["humidity_pct"] > 100.0
            or oor["humidity_pct"] < 0.0
            or oor["gas_raw"] < 0
            or oor["gas_raw"] > 4095
            or oor["noise_raw"] < 0
            or oor["noise_raw"] > 4095
        )
        assert is_out


def test_generate_intermittent_scenario(generator):
    """Verify sequence of alternating valid and null readings."""
    seq = generator.generate_intermittent_scenario(steps=6)
    assert len(seq) == 6
    assert seq[0]["temperature_c"] is not None
    assert seq[1]["temperature_c"] is None
    assert seq[2]["temperature_c"] is not None
    assert seq[3]["temperature_c"] is None


def test_to_serial_line_strips_internal_metadata(generator):
    """Verify to_serial_line outputs clean newline-delimited JSON without _ metadata keys."""
    pkt = generator.generate_normal()
    assert "_simulated_test_data" in pkt
    assert "_scenario" in pkt

    line = generator.to_serial_line(pkt)
    assert line.endswith("\n")

    decoded = json.loads(line)
    assert "_simulated_test_data" not in decoded
    assert "_scenario" not in decoded
    assert decoded["device_id"] == "test-esp32-node"
    assert "temperature_c" in decoded

