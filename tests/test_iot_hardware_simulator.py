# -*- coding: utf-8 -*-
"""
Tests for simulator.py (IoTHardwareSimulator and read_sensors).
Verifies realistic sensor reading generation, threshold evaluation, scenario overrides,
and node telemetry structure.
"""

import pytest
from simulator import IoTHardwareSimulator, SCENARIOS, SENSOR_NODES, get_simulator, read_sensors


def test_sensor_nodes_definition():
    """Verify all 4 required hardware nodes exist."""
    assert len(SENSOR_NODES) == 4
    node_ids = [n["node"] for n in SENSOR_NODES]
    assert "GAS-01" in node_ids
    assert "DHT-02" in node_ids
    assert "PM-03" in node_ids
    assert "MIC-04" in node_ids


def test_read_sensors_structure():
    """Verify read_sensors returns the required schema."""
    telemetry = read_sensors()
    assert "readings" in telemetry
    assert "site_status" in telemetry
    assert "danger_count" in telemetry
    assert "warning_count" in telemetry
    assert "safe_count" in telemetry
    assert "recommended_action" in telemetry
    assert "nodes" in telemetry

    readings = telemetry["readings"]
    for param in ["temperature", "humidity", "dust", "noise", "gas"]:
        assert param in readings
        r = readings[param]
        assert "value" in r
        assert "unit" in r
        assert "status" in r
        assert r["status"] in ("SAFE", "WARNING", "DANGER")
        assert "min" in r
        assert "max" in r
        assert "warn" in r
        assert "danger" in r


def test_scenario_presets():
    """Verify demo presets correctly override values."""
    sim = IoTHardwareSimulator()

    # All Safe
    sim.set_override(SCENARIOS["All Safe"])
    tel = sim.read_sensors()
    assert tel["site_status"] == "normal"
    assert tel["danger_count"] == 0

    # Gas Leak Danger
    sim.set_override(SCENARIOS["Gas Leak Danger"])
    tel = sim.read_sensors()
    assert tel["site_status"] == "critical"
    assert tel["danger_count"] >= 1
    assert tel["readings"]["gas"]["status"] == "DANGER"

    # Dust & Noise
    sim.set_override(SCENARIOS["Dust & Noise"])
    tel = sim.read_sensors()
    assert tel["site_status"] == "warning"
    assert tel["readings"]["dust"]["status"] == "WARNING"
    assert tel["readings"]["noise"]["status"] == "WARNING"

    # Clear override
    sim.clear_override()
    assert sim.override_active is False
