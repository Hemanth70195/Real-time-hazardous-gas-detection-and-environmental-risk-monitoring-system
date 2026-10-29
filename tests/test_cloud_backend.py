# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Cloud IoT Streaming & Backend Test Suite (Phase 3 & 4).
Tests the FastAPI ingestion endpoint, database persistence, stale detection,
API key security, and CloudSensorReceiver integration under the Phase 4 4-sensor schema.
"""

import time
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import app
from backend.database import Base, get_db
from backend.config import SAFEEDGE_API_KEY, STALE_TIMEOUT_SECONDS
from core.cloud_sensor_receiver import CloudSensorReceiver


from sqlalchemy.pool import StaticPool

# In-memory SQLite for isolated, hermetic backend testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    # Provide default auth header
    c = TestClient(app)
    c.headers.update({"X-API-Key": SAFEEDGE_API_KEY})
    return c


# =============================================================================
# 1. Ingestion Endpoint Tests (Phase 4 4-Sensor Telemetry)
# =============================================================================

def test_ingest_valid_phase4_telemetry_without_dust(client):
    """
    Verify POST /api/v1/telemetry successfully accepts the Phase 4 payload
    without any dust fields and persists it into the database.
    """
    payload = {
        "device_id": "safeedge-esp32-01",
        "temperature_c": 31.5,
        "humidity_pct": 64.0,
        "gas_raw": 1250.0,
        "noise_raw": 1850.0,
    }
    response = client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["device_id"] == "safeedge-esp32-01"
    assert data["reading_id"] > 0

    # Verify persisted telemetry via latest query
    latest_resp = client.get("/api/v1/telemetry/latest?device_id=safeedge-esp32-01")
    assert latest_resp.status_code == 200
    latest = latest_resp.json()
    telemetry = latest["telemetry"]
    assert telemetry["device_id"] == "safeedge-esp32-01"
    assert telemetry["temperature_c"] == 31.5
    assert telemetry["humidity_pct"] == 64.0
    assert telemetry["gas_raw"] == 1250.0
    assert telemetry["noise_raw"] == 1850.0
    # Dust fields must not be present
    assert "pm1_0" not in telemetry
    assert "pm10" not in telemetry
    # Calibration flags must confirm raw ADC integrity
    assert telemetry["is_gas_calibrated"] is False
    assert telemetry["is_noise_calibrated"] is False


def test_ingest_partial_telemetry_with_null_sensors(client):
    """
    Verify disconnected sensors (represented as null) do not reject the payload.
    """
    payload = {
        "device_id": "safeedge-esp32-01",
        "temperature_c": None,
        "humidity_pct": None,
        "gas_raw": 1400.0,
        "noise_raw": 1600.0,
    }
    response = client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    latest_resp = client.get("/api/v1/telemetry/latest?device_id=safeedge-esp32-01")
    assert latest_resp.status_code == 200
    telemetry = latest_resp.json()["telemetry"]
    assert telemetry["temperature_c"] is None
    assert telemetry["humidity_pct"] is None
    assert telemetry["gas_raw"] == 1400.0
    assert telemetry["noise_raw"] == 1600.0


def test_ingest_legacy_payload_extra_dust_fields_ignored(client):
    """
    Verify backward compatibility: if a legacy device sends pm1_0/pm10,
    the backend ignores extra dust fields and does not fail validation.
    """
    payload = {
        "device_id": "safeedge-esp32-01",
        "temperature_c": 28.0,
        "humidity_pct": 55.0,
        "gas_raw": 1100.0,
        "noise_raw": 1500.0,
        "pm1_0": 12.0,
        "pm10": 45.0,
    }
    response = client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    latest_resp = client.get("/api/v1/telemetry/latest?device_id=safeedge-esp32-01")
    assert latest_resp.status_code == 200
    telemetry = latest_resp.json()["telemetry"]
    assert telemetry["temperature_c"] == 28.0
    assert "pm1_0" not in telemetry
    assert "pm10" not in telemetry


def test_ingest_invalid_bounds_rejected(client):
    """Verify impossible physical bounds are rejected with 422 Unprocessable Entity."""
    # Temperature > 85 °C
    bad_temp = {
        "device_id": "safeedge-esp32-01",
        "temperature_c": 120.0,
        "humidity_pct": 50.0,
        "gas_raw": 1200.0,
        "noise_raw": 1500.0,
    }
    assert client.post("/api/v1/telemetry", json=bad_temp).status_code == 422

    # Negative ADC count
    bad_adc = {
        "device_id": "safeedge-esp32-01",
        "temperature_c": 25.0,
        "humidity_pct": 50.0,
        "gas_raw": -50.0,
        "noise_raw": 1500.0,
    }
    assert client.post("/api/v1/telemetry", json=bad_adc).status_code == 422


def test_api_key_authentication():
    """Verify unauthorized request without API key header is rejected with 401."""
    raw_client = TestClient(app)
    payload = {
        "device_id": "safeedge-esp32-01",
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "gas_raw": 1200.0,
        "noise_raw": 1500.0,
    }
    # No header -> 401
    resp_no_auth = raw_client.post("/api/v1/telemetry", json=payload)
    assert resp_no_auth.status_code == 401

    # Bad header -> 401
    resp_bad_auth = raw_client.post("/api/v1/telemetry", json=payload, headers={"X-API-Key": "wrong-key"})
    assert resp_bad_auth.status_code == 401

    # Valid header -> 200
    resp_ok = raw_client.post("/api/v1/telemetry", json=payload, headers={"X-API-Key": SAFEEDGE_API_KEY})
    assert resp_ok.status_code == 200


# =============================================================================
# 2. Latest Telemetry & Freshness / Stale Detection
# =============================================================================

def test_get_latest_telemetry_fresh_and_hazard_assessed(client):
    """
    Verify GET /api/v1/telemetry/latest returns fresh telemetry and runs
    the hazard assessment engine without dust parameters.
    """
    client.post("/api/v1/telemetry", json={
        "device_id": "safeedge-esp32-01",
        "temperature_c": 36.5,  # Trigger warning
        "humidity_pct": 55.0,
        "gas_raw": 1300.0,
        "noise_raw": 1700.0,
    })

    response = client.get("/api/v1/telemetry/latest?device_id=safeedge-esp32-01")
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "safeedge-esp32-01"
    assert data["is_connected"] is True
    assert data["is_stale"] is False
    assert data["telemetry"]["temperature_c"] == 36.5

    # Hazard assessment must NOT contain dust
    hazard = data["hazard_assessment"]
    assert hazard is not None
    assert "dust" not in hazard["all_assessments"]
    assert "temperature" in hazard["all_assessments"]
    assert hazard["all_assessments"]["temperature"]["status"] == "WARNING"


def test_get_latest_telemetry_stale_detection(client):
    """Verify stale detection flags is_stale=True when timeout is exceeded."""
    client.post("/api/v1/telemetry", json={
        "device_id": "safeedge-esp32-01",
        "temperature_c": 24.0,
        "humidity_pct": 45.0,
        "gas_raw": 1200.0,
        "noise_raw": 1500.0,
    })

    # Query with 0.001 second stale threshold to simulate passage of time
    time.sleep(0.02)
    response = client.get("/api/v1/telemetry/latest?device_id=safeedge-esp32-01&stale_threshold_seconds=0.001")
    data = response.json()
    assert data["is_stale"] is True
    assert data["last_seen_seconds_ago"] is not None
    # Stale readings bypass hazard evaluation
    assert data["hazard_assessment"] is None


# =============================================================================
# 3. Telemetry History & Time Series
# =============================================================================

def test_get_telemetry_history(client):
    """Verify historical time series querying returns ordered readings."""
    for i in range(5):
        client.post("/api/v1/telemetry", json={
            "device_id": "safeedge-esp32-01",
            "temperature_c": 20.0 + i,
            "humidity_pct": 50.0 + i,
            "gas_raw": 1000.0 + i * 50,
            "noise_raw": 1500.0 + i * 50,
        })

    response = client.get("/api/v1/telemetry/history?device_id=safeedge-esp32-01&limit=10")
    assert response.status_code == 200
    records = response.json()
    assert len(records) == 5
    # Chronological ascending order check for dashboard charts
    assert records[0]["temperature_c"] == 20.0
    assert records[-1]["temperature_c"] == 24.0


# =============================================================================
# 4. CloudSensorReceiver Dashboard Integration
# =============================================================================

def test_cloud_sensor_receiver_mapping_phase4(client):
    """
    Verify CloudSensorReceiver maps cloud backend data into the 4-parameter
    dashboard format without dust.
    """
    receiver = CloudSensorReceiver(backend_url="http://testserver", device_id="safeedge-esp32-01")

    mock_backend_response = {
        "device_id": "safeedge-esp32-01",
        "is_connected": True,
        "is_stale": False,
        "status": "ONLINE",
        "last_seen_seconds_ago": 1.2,
        "telemetry": {
            "server_timestamp": datetime.now().isoformat(),
            "temperature_c": 29.5,
            "humidity_pct": 62.0,
            "gas_raw": 1250.0,
            "noise_raw": 1850.0,
        },
    }

    result = receiver._build_live_cloud_response(mock_backend_response)
    assert result["data_source"] == "cloud_esp32"
    assert result["total_count"] == 4
    readings = result["readings"]

    # Verify 4 monitored channels
    assert "temperature" in readings
    assert "humidity" in readings
    assert "noise" in readings
    assert "gas" in readings
    # Verify dust is completely absent
    assert "dust" not in readings

    # Verify uncalibrated flags
    assert readings["gas"]["is_uncalibrated"] is True
    assert readings["gas"]["unit"] == "ADC"
    assert readings["noise"]["is_uncalibrated"] is True
    assert readings["noise"]["unit"] == "ADC"

    # Verify nodes definition has 3 physical nodes
    assert len(result["nodes"]) == 3
    node_names = [n["node"] for n in result["nodes"]]
    assert "PM-03" not in node_names


# =============================================================================
# 5. Advanced Backend & Database Reliability Tests (Phase 5)
# =============================================================================

def test_device_timestamp_handling(client):
    """Verify backend records server timestamp and parses optional device timestamp."""
    payload = {
        "device_id": "safeedge-esp32-01",
        "temperature_c": 25.0,
        "humidity_pct": 50.0,
        "gas_raw": 1200.0,
        "noise_raw": 1500.0,
        "device_timestamp": "2026-10-29T12:00:00Z",
    }
    resp = client.post("/api/v1/telemetry", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["server_timestamp"] is not None

    latest_resp = client.get("/api/v1/telemetry/latest?device_id=safeedge-esp32-01")
    telemetry = latest_resp.json()["telemetry"]
    assert telemetry["device_timestamp"] == "2026-10-29T12:00:00Z"
    assert telemetry["server_timestamp"] is not None


def test_device_registry_listing(client):
    """Verify registered devices appear in GET /api/v1/devices with online status."""
    client.post("/api/v1/telemetry", json={
        "device_id": "safeedge-esp32-alpha",
        "temperature_c": 22.0,
        "humidity_pct": 48.0,
        "gas_raw": 1100.0,
        "noise_raw": 1400.0,
    })
    client.post("/api/v1/telemetry", json={
        "device_id": "safeedge-esp32-beta",
        "temperature_c": 24.0,
        "humidity_pct": 52.0,
        "gas_raw": 1150.0,
        "noise_raw": 1450.0,
    })

    devices_resp = client.get("/api/v1/devices")
    assert devices_resp.status_code == 200
    devices = devices_resp.json()
    device_ids = [d["device_id"] for d in devices]
    assert "safeedge-esp32-alpha" in device_ids
    assert "safeedge-esp32-beta" in device_ids


def test_history_filtering_by_device_and_hours(client):
    """Verify history queries isolate readings by device ID and respect time windows."""
    # Post readings for Device A
    client.post("/api/v1/telemetry", json={
        "device_id": "device-A",
        "temperature_c": 22.0,
        "humidity_pct": 45.0,
        "gas_raw": 1100.0,
        "noise_raw": 1500.0,
    })
    # Post readings for Device B
    client.post("/api/v1/telemetry", json={
        "device_id": "device-B",
        "temperature_c": 35.0,
        "humidity_pct": 70.0,
        "gas_raw": 2200.0,
        "noise_raw": 2500.0,
    })

    # Query Device A history
    resp_a = client.get("/api/v1/telemetry/history?device_id=device-A&hours=1.0")
    assert resp_a.status_code == 200
    records_a = resp_a.json()
    assert len(records_a) == 1
    assert records_a[0]["device_id"] == "device-A"
    assert records_a[0]["temperature_c"] == 22.0

    # Query Device B history
    resp_b = client.get("/api/v1/telemetry/history?device_id=device-B&hours=1.0")
    assert resp_b.status_code == 200
    records_b = resp_b.json()
    assert len(records_b) == 1
    assert records_b[0]["device_id"] == "device-B"
    assert records_b[0]["temperature_c"] == 35.0


def test_rapid_burst_ingestion(client):
    """Verify consecutive rapid-burst payloads are ingested without deadlock."""
    for i in range(15):
        resp = client.post("/api/v1/telemetry", json={
            "device_id": "burst-device",
            "temperature_c": 20.0 + (i * 0.1),
            "humidity_pct": 50.0,
            "gas_raw": 1200.0,
            "noise_raw": 1600.0,
        })
        assert resp.status_code == 200

    history_resp = client.get("/api/v1/telemetry/history?device_id=burst-device&limit=50")
    assert history_resp.status_code == 200
    assert len(history_resp.json()) == 15

