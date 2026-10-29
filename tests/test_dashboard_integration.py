# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Dashboard & Multi-Source Integration Test Suite (Phase 5).
Verifies that the dashboard components, data source switching, state preservation,
stale-data flagging, and CSV/JSON reporting work reliably without physical hardware:
1. Simulation Mode data flow.
2. USB Serial Mode with mocked ESP32 data.
3. Cloud Mode with mocked backend responses.
4. Distinguishing simulated, live, raw, and unavailable readings.
5. Stale data handling and connection status updates.
6. Missing/null sensor resilience.
7. Mode switching state preservation.
8. Raw sensor integrity (uncalibrated ADC, no ppm or dB conversion).
9. CSV and JSON report export validity.
"""

import json
import time
import pytest
from core.serial_sensor_receiver import SerialSensorReceiver, SerialConnectionStatus, get_serial_receiver
from core.cloud_sensor_receiver import CloudSensorReceiver
from core.hazard_assessment import HazardAssessmentEngine, HazardStatus
from core.hazard_history import HazardHistoryTracker
from simulator import IoTHardwareSimulator, SCENARIOS


@pytest.fixture
def clean_simulator():
    """Provides a fresh IoTHardwareSimulator instance."""
    return IoTHardwareSimulator()


@pytest.fixture
def clean_serial_receiver():
    """Provides an isolated SerialSensorReceiver instance."""
    rec = SerialSensorReceiver(stale_timeout_seconds=0.3)
    rec.disconnect()
    return rec


# =============================================================================
# 1. Simulation Mode Data Flow
# =============================================================================

def test_dashboard_simulation_mode_flow(clean_simulator):
    """Verify simulation mode generates valid readings across all 4 parameters."""
    clean_simulator.set_data_source("simulation")
    data = clean_simulator.read_sensors(data_source="simulation")

    assert data["data_source"] == "simulation"
    assert data["is_stale"] is False
    assert data["total_count"] == 4
    readings = data["readings"]

    # Monitored parameters
    assert "temperature" in readings
    assert "humidity" in readings
    assert "noise" in readings
    assert "gas" in readings
    assert "dust" not in readings

    # Simulated gas is in ppm, noise in dB
    assert readings["gas"]["unit"] == "ppm"
    assert readings["noise"]["unit"] == "dB"
    assert readings["gas"]["is_uncalibrated"] is False


# =============================================================================
# 2. USB Serial Mode with Mocked ESP32 Telemetry
# =============================================================================

def test_dashboard_serial_mode_with_mocked_data(clean_simulator, clean_serial_receiver):
    """Verify Live Hardware Mode ingests mocked serial data without physical COM port."""
    msg = json.dumps({
        "device_id": "safeedge-esp32-mock",
        "temperature_c": 27.5,
        "humidity_pct": 58.0,
        "gas_raw": 1350,
        "noise_raw": 1900,
    })
    clean_serial_receiver.feed_mock_message(msg)

    # Monkeypatch the singleton for clean_simulator call
    import simulator
    original_receiver = simulator.get_serial_receiver
    simulator.get_serial_receiver = lambda: clean_serial_receiver

    try:
        data = clean_simulator.read_sensors(data_source="live_esp32")
        assert data["data_source"] == "live_esp32"
        assert data["device_id"] == "safeedge-esp32-mock"
        assert data["is_stale"] is False
        assert data["total_count"] == 4
        readings = data["readings"]

        # Calibrated channels
        assert readings["temperature"]["value"] == 27.5
        assert readings["temperature"]["unit"] == "°C"
        assert readings["humidity"]["value"] == 58.0
        assert readings["humidity"]["unit"] == "%"

        # Raw ADC channels (MUST NOT be ppm or dB)
        assert readings["gas"]["value"] == 1350.0
        assert readings["gas"]["unit"] == "ADC"
        assert readings["gas"]["is_uncalibrated"] is True
        assert readings["gas"]["status"] == "UNCALIBRATED"

        assert readings["noise"]["value"] == 1900.0
        assert readings["noise"]["unit"] == "ADC"
        assert readings["noise"]["is_uncalibrated"] is True
        assert readings["noise"]["status"] == "UNCALIBRATED"

    finally:
        simulator.get_serial_receiver = original_receiver


# =============================================================================
# 3. Cloud Mode with Mocked Backend Response
# =============================================================================

def test_dashboard_cloud_mode_with_mocked_backend():
    """Verify CloudSensorReceiver maps cloud responses into dashboard schema."""
    receiver = CloudSensorReceiver(backend_url="http://mocked-backend", device_id="safeedge-esp32-cloud")

    backend_payload = {
        "device_id": "safeedge-esp32-cloud",
        "is_connected": True,
        "is_stale": False,
        "status": "ONLINE",
        "last_seen_seconds_ago": 0.8,
        "telemetry": {
            "server_timestamp": "2026-10-29T12:00:00Z",
            "temperature_c": 31.0,
            "humidity_pct": 65.0,
            "gas_raw": 1280.0,
            "noise_raw": 1820.0,
        },
    }

    dash_data = receiver._build_live_cloud_response(backend_payload)
    assert dash_data["data_source"] == "cloud_esp32"
    assert dash_data["is_stale"] is False
    assert dash_data["total_count"] == 4
    readings = dash_data["readings"]

    assert readings["temperature"]["value"] == 31.0
    assert readings["humidity"]["value"] == 65.0
    assert readings["gas"]["value"] == 1280.0
    assert readings["gas"]["unit"] == "ADC"
    assert readings["gas"]["is_uncalibrated"] is True
    assert readings["noise"]["value"] == 1820.0
    assert readings["noise"]["unit"] == "ADC"
    assert readings["noise"]["is_uncalibrated"] is True


# =============================================================================
# 4. Stale Data Handling in Dashboard
# =============================================================================

def test_dashboard_stale_data_handling(clean_simulator, clean_serial_receiver):
    """Verify stale data is flagged and not displayed as active current readings."""
    msg = json.dumps({
        "device_id": "esp32-stale",
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "gas_raw": 1200,
        "noise_raw": 1500,
    })
    clean_serial_receiver.feed_mock_message(msg)

    import simulator
    original_receiver = simulator.get_serial_receiver
    simulator.get_serial_receiver = lambda: clean_serial_receiver

    try:
        # Initially fresh
        data_fresh = clean_simulator.read_sensors(data_source="live_esp32")
        assert data_fresh["is_stale"] is False
        assert data_fresh["readings"] is not None

        # Wait past the 0.3s stale timeout
        time.sleep(0.4)
        data_stale = clean_simulator.read_sensors(data_source="live_esp32")
        assert data_stale["is_stale"] is True
        assert data_stale["readings"] is None
        assert data_stale["site_status"] == "warning"

    finally:
        simulator.get_serial_receiver = original_receiver


# =============================================================================
# 5. Missing / Null Sensor Resilience
# =============================================================================

def test_dashboard_missing_sensors_resilience(clean_simulator, clean_serial_receiver):
    """Verify disconnected sensors (nulls) do not crash the sensor reader or assessment."""
    msg = json.dumps({
        "device_id": "esp32-partial",
        "temperature_c": None,  # DHT disconnected
        "humidity_pct": None,
        "gas_raw": 1400,
        "noise_raw": None,      # Mic disconnected
    })
    clean_serial_receiver.feed_mock_message(msg)

    import simulator
    original_receiver = simulator.get_serial_receiver
    simulator.get_serial_receiver = lambda: clean_serial_receiver

    try:
        data = clean_simulator.read_sensors(data_source="live_esp32")
        readings = data["readings"]
        assert readings["temperature"]["value"] is None
        assert readings["temperature"]["status"] == "OFFLINE"
        assert readings["humidity"]["value"] is None
        assert readings["humidity"]["status"] == "OFFLINE"
        assert readings["gas"]["value"] == 1400.0
        assert readings["noise"]["value"] is None
        assert readings["noise"]["status"] == "OFFLINE"

    finally:
        simulator.get_serial_receiver = original_receiver


# =============================================================================
# 6. Mode Switching State Preservation
# =============================================================================

def test_mode_switching_state_preservation():
    """Verify switching data sources maintains historical events and unrelated parameters."""
    tracker = HazardHistoryTracker()

    # Step 1: Record Simulation Snapshot
    sim_readings = {"temperature": 24.0, "humidity": 50.0, "gas": 8.0, "noise": 65.0}
    tracker.record_snapshot(sim_readings, tick=1, data_source="simulation")

    # Step 2: Switch to Serial Live Mode and record snapshot
    serial_readings = {"temperature": 28.0, "humidity": 60.0, "gas": 1200.0, "noise": 1800.0}
    tracker.record_snapshot(serial_readings, tick=2, data_source="live_esp32", device_id="safeedge-esp32-01")

    # Step 3: Switch to Cloud Live Mode and record snapshot
    cloud_readings = {"temperature": 29.0, "humidity": 62.0, "gas": 1250.0, "noise": 1850.0}
    tracker.record_snapshot(cloud_readings, tick=3, data_source="cloud_esp32", device_id="safeedge-esp32-01")

    df = tracker.get_snapshots_dataframe()
    assert len(df) == 3
    sources = list(df["Data_Source"])
    assert sources == ["simulation", "live_esp32", "cloud_esp32"]

    # History summary preserves count across all sources
    summary = tracker.get_summary_statistics()
    assert summary["total_snapshots"] == 3


# =============================================================================
# 7. CSV and JSON Report Exports Integrity
# =============================================================================

def test_report_exports_no_dust_and_accurate_labels():
    """Verify CSV and JSON report exports exclude dust and identify calibration status."""
    tracker = HazardHistoryTracker()

    tracker.record_snapshot(
        {"temperature": 25.0, "humidity": 50.0, "gas": 1200.0, "noise": 1600.0},
        tick=1,
        data_source="live_esp32",
        device_id="safeedge-esp32-01",
    )

    # 1. Verify CSV Export
    csv_text = tracker.export_readings_csv()
    assert "Dust" not in csv_text
    assert "PM1.0" not in csv_text
    assert "PM2.5" not in csv_text
    assert "PM10" not in csv_text
    assert "Temperature (deg C)" in csv_text
    assert "Relative Humidity (%)" in csv_text
    assert "Raw Gas MQ135 (ADC)" in csv_text
    assert "Gas Calibration Status" in csv_text

    # 2. Verify JSON Export
    json_report = tracker.export_json_report()
    assert len(json_report["historical_readings"]) == 1
    reading = json_report["historical_readings"][0]
    assert "dust" not in reading
    assert "pm1_0" not in reading
    assert reading["Data_Source"] == "live_esp32"
    assert reading["gas_calibration_status"] == "Uncalibrated Raw ADC"
