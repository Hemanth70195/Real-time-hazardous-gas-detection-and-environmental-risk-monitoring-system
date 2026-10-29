# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - End-to-End Hardware-Independent Simulation Suite (Phase 5).
Verifies the complete data pipeline end-to-end across two transmission modalities:
1. USB Serial Telemetry Pipeline:
   MockESP32Generator -> SerialSensorReceiver -> IoTHardwareSimulator -> HazardAssessmentEngine -> HazardHistoryTracker -> CSV/JSON Export

2. Cloud IoT Ingestion Pipeline:
   MockESP32Generator -> FastAPI Telemetry Endpoint -> Database Persistence -> Latest Telemetry Query -> CloudSensorReceiver -> HazardHistoryTracker -> CSV/JSON Export
"""

import json
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import app
from backend.database import Base, get_db
from backend.config import SAFEEDGE_API_KEY
from backend.models import TelemetryReading, Device
from core.serial_sensor_receiver import SerialSensorReceiver
from core.cloud_sensor_receiver import CloudSensorReceiver
from core.hazard_assessment import HazardAssessmentEngine, HazardStatus
from core.hazard_history import HazardHistoryTracker
from simulator import IoTHardwareSimulator
from tools.mock_esp32_generator import MockESP32TelemetryGenerator


# =============================================================================
# Database Fixture for Isolated End-to-End Cloud Tests
# =============================================================================

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    c = TestClient(app)
    c.headers.update({"X-API-Key": SAFEEDGE_API_KEY})
    return c


@pytest.fixture
def generator():
    return MockESP32TelemetryGenerator(device_id="safeedge-esp32-e2e")


# =============================================================================
# Test 1: Complete USB Serial Data Pipeline
# =============================================================================

def test_e2e_serial_pipeline(generator):
    """
    Traces telemetry flow:
    Generator -> Serial Receiver -> Simulator Reader -> Hazard Assessment -> History Tracker -> Export
    """
    # 1. Generate normal and spike mock telemetry
    norm_pkt = generator.generate_normal()
    spike_pkt = generator.generate_high_temperature(37.5)

    receiver = SerialSensorReceiver(default_baud_rate=115200)
    tracker = HazardHistoryTracker()
    sim = IoTHardwareSimulator()

    # Feed normal reading
    norm_line = generator.to_serial_line(norm_pkt)
    parsed_norm = receiver.feed_mock_message(norm_line)
    assert parsed_norm is not None
    assert parsed_norm.device_id == "safeedge-esp32-e2e"

    # Assess via Hazard Assessment Engine
    meta = {
        "temperature": {"display_name": "Temperature", "unit": "°C", "thresholds": {"safe_min": 15, "safe_max": 30, "warning_min": 5, "warning_max": 35}},
        "humidity": {"display_name": "Humidity", "unit": "%", "thresholds": {"safe_min": 30, "safe_max": 60, "warning_min": 20, "warning_max": 80}},
        "gas": {"display_name": "Gas Concentration", "unit": "ppm"},
        "noise": {"display_name": "Noise Level", "unit": "dB"},
    }
    ass_norm = HazardAssessmentEngine.assess_esp32_reading(parsed_norm, meta)
    assert ass_norm.data_source == "live_esp32"
    assert ass_norm.overall_status != HazardStatus.SAFE  # Raw ADC is never marked safe
    assert ass_norm.uncalibrated_count == 2
    assert ass_norm.all_assessments["gas"].is_uncalibrated is True
    assert ass_norm.all_assessments["gas"].is_safe is False

    # Record in history tracker
    tracker.record_snapshot(
        readings={"temperature": parsed_norm.temperature_c, "humidity": parsed_norm.humidity_pct, "gas": parsed_norm.gas_raw, "noise": parsed_norm.noise_raw},
        tick=1,
        data_source="live_esp32",
        device_id="safeedge-esp32-e2e",
        extra_data={"gas_raw": parsed_norm.gas_raw, "noise_raw": parsed_norm.noise_raw},
    )

    # Feed high temperature spike (37.5 °C > warning_max 35.0 -> DANGER)
    spike_line = generator.to_serial_line(spike_pkt)
    parsed_spike = receiver.feed_mock_message(spike_line)
    ass_spike = HazardAssessmentEngine.assess_esp32_reading(parsed_spike, meta)
    assert ass_spike.all_assessments["temperature"].status == HazardStatus.DANGER

    tracker.record_snapshot(
        readings={"temperature": parsed_spike.temperature_c, "humidity": parsed_spike.humidity_pct, "gas": parsed_spike.gas_raw, "noise": parsed_spike.noise_raw},
        tick=2,
        data_source="live_esp32",
        device_id="safeedge-esp32-e2e",
        extra_data={"gas_raw": parsed_spike.gas_raw, "noise_raw": parsed_spike.noise_raw},
    )

    # Verify history accumulation
    assert tracker.snapshot_count == 2
    df = tracker.get_snapshots_dataframe()
    assert len(df) == 2
    assert list(df["Data_Source"]) == ["live_esp32", "live_esp32"]
    assert list(df["temperature"]) == [parsed_norm.temperature_c, 37.5]

    # Verify CSV and JSON Exports
    csv_report = tracker.export_readings_csv()
    assert "safeedge-esp32-e2e" in csv_report
    assert "Uncalibrated Raw ADC" in csv_report
    assert "Dust" not in csv_report

    json_report = tracker.export_json_report()
    assert len(json_report["historical_readings"]) == 2
    assert json_report["historical_readings"][1]["temperature"] == 37.5


# =============================================================================
# Test 2: Complete Cloud Ingestion & Dashboard Retrieval Pipeline
# =============================================================================

def test_e2e_cloud_pipeline(client, generator):
    """
    Traces telemetry flow:
    Generator -> FastAPI POST -> Database -> Latest Telemetry Query -> Cloud Receiver -> History Tracker -> Export
    """
    raw_pkt = generator.generate_gas_spike(3200)
    clean_payload = {k: v for k, v in raw_pkt.items() if not k.startswith("_")}

    # 1. Ingest via HTTPS endpoint
    ingest_resp = client.post("/api/v1/telemetry", json=clean_payload)
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["status"] == "success"

    # 2. Query latest telemetry from backend
    latest_resp = client.get(f"/api/v1/telemetry/latest?device_id={generator.device_id}")
    assert latest_resp.status_code == 200
    latest_data = latest_resp.json()
    assert latest_data["is_connected"] is True
    assert latest_data["is_stale"] is False
    assert latest_data["telemetry"]["gas_raw"] == 3200.0

    # 3. CloudSensorReceiver maps to Streamlit schema
    cloud_rec = CloudSensorReceiver(backend_url="http://mocked", device_id=generator.device_id)
    dash_data = cloud_rec._build_live_cloud_response(latest_data)
    assert dash_data["data_source"] == "cloud_esp32"
    assert dash_data["readings"]["gas"]["value"] == 3200.0
    assert dash_data["readings"]["gas"]["is_uncalibrated"] is True
    assert dash_data["readings"]["gas"]["unit"] == "ADC"

    # 4. Record to History Tracker
    tracker = HazardHistoryTracker()
    tracker.record_snapshot(
        readings={
            "temperature": dash_data["readings"]["temperature"]["value"],
            "humidity": dash_data["readings"]["humidity"]["value"],
            "gas": dash_data["readings"]["gas"]["value"],
            "noise": dash_data["readings"]["noise"]["value"],
        },
        tick=1,
        data_source="cloud_esp32",
        device_id=generator.device_id,
        extra_data={"gas_raw": 3200.0, "noise_raw": dash_data["readings"]["noise"]["value"]},
    )

    assert tracker.snapshot_count == 1
    report = tracker.export_json_report()
    assert report["historical_readings"][0]["Data_Source"] == "cloud_esp32"
    assert report["historical_readings"][0]["gas_raw"] == 3200.0
