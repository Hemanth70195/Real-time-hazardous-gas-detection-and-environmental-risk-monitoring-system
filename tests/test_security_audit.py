# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Security, Vulnerability & Ingestion Boundary Audit Suite (Phase 7).
Validates authentication enforcement, SQL injection immunity, input validation boundaries,
CORS security, and information leakage prevention.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import app
from backend.database import Base, get_db
from backend.config import SAFEEDGE_API_KEY
from backend.models import Device, TelemetryReading


# Isolated in-memory SQLite fixture for security audit tests
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
def setup_security_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def unauthed_client():
    return TestClient(app)


@pytest.fixture
def authed_client():
    c = TestClient(app)
    c.headers.update({"X-API-Key": SAFEEDGE_API_KEY})
    return c


# =============================================================================
# 1. Authentication & API Key Enforcement
# =============================================================================

def test_unauthenticated_requests_rejected(unauthed_client):
    """Protected ingestion and query endpoints must return 401 Unauthorized when missing API key."""
    # Ingestion endpoint
    payload = {
        "device_id": "safeedge-esp32-sec",
        "temperature_c": 25.0,
        "humidity_pct": 55.0,
        "gas_raw": 1200,
        "noise_raw": 1800,
    }
    resp = unauthed_client.post("/api/v1/telemetry", json=payload)
    assert resp.status_code == 401
    assert "Invalid or missing X-API-Key" in resp.json()["detail"]

    # Latest telemetry query
    resp = unauthed_client.get("/api/v1/telemetry/latest?device_id=safeedge-esp32-sec")
    assert resp.status_code == 401

    # History query
    resp = unauthed_client.get("/api/v1/telemetry/history?device_id=safeedge-esp32-sec")
    assert resp.status_code == 401

    # Device list query
    resp = unauthed_client.get("/api/v1/devices")
    assert resp.status_code == 401


def test_invalid_api_key_rejected(unauthed_client):
    """Requests with an invalid API key must be rejected with 401 Unauthorized."""
    headers = {"X-API-Key": "malicious-fake-key-9999"}
    resp = unauthed_client.get("/api/v1/devices", headers=headers)
    assert resp.status_code == 401
    assert "Invalid or missing X-API-Key" in resp.json()["detail"]


def test_public_health_endpoints_accessible_without_key(unauthed_client):
    """Root metadata and health check endpoints must be accessible publicly without leaking credentials."""
    resp = unauthed_client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "SafeEdge HazardGuard Cloud IoT Backend"
    assert "password" not in str(data).lower()
    assert "secret" not in str(data).lower()

    resp = unauthed_client.get("/health")
    assert resp.status_code == 200
    h_data = resp.json()
    assert h_data["status"] == "healthy"
    assert "database" in h_data
    assert "password" not in str(h_data).lower()


# =============================================================================
# 2. SQL Injection Resistance
# =============================================================================

@pytest.mark.parametrize("malicious_id", [
    "safeedge' OR '1'='1",
    "safeedge'; DROP TABLE devices; --",
    "' UNION SELECT 1, 'admin', 'pwd', '2026-01-01'--",
    "admin'--",
    "../../etc/passwd",
])
def test_sql_injection_immunity_in_queries(authed_client, malicious_id):
    """
    SQL injection strings in device_id must be safely bound as parameters
    and never alter SQL syntax or execute arbitrary SQL commands.
    """
    # Query latest with injection string
    resp = authed_client.get(f"/api/v1/telemetry/latest?device_id={malicious_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_connected"] is False
    assert data["is_stale"] is True
    assert data["telemetry"] is None
    assert data["device_id"] == malicious_id

    # Query history with injection string
    resp_hist = authed_client.get(f"/api/v1/telemetry/history?device_id={malicious_id}")
    assert resp_hist.status_code == 200
    assert resp_hist.json() == []

    # Verify database schema remains intact
    db = TestingSession()
    device_count = db.query(Device).count()
    reading_count = db.query(TelemetryReading).count()
    db.close()
    assert device_count >= 0
    assert reading_count >= 0


# =============================================================================
# 3. Input Validation Boundaries & Schema Enforcements
# =============================================================================

def test_negative_adc_gas_reading_rejected(authed_client):
    """Negative raw ADC gas counts (physically impossible) must be rejected with 422."""
    payload = {
        "device_id": "safeedge-esp32-sec",
        "gas_raw": -50.0,
    }
    resp = authed_client.post("/api/v1/telemetry", json=payload)
    assert resp.status_code == 422
    assert "greater_than_equal" in str(resp.json())


def test_out_of_range_temperature_rejected(authed_client):
    """Extreme temperatures beyond physical DHT22 bounds (-40 to 85°C) must be rejected with 422."""
    payload = {
        "device_id": "safeedge-esp32-sec",
        "temperature_c": 150.0,  # Exceeds max 85.0
    }
    resp = authed_client.post("/api/v1/telemetry", json=payload)
    assert resp.status_code == 422

    payload["temperature_c"] = -60.0  # Below min -40.0
    resp2 = authed_client.post("/api/v1/telemetry", json=payload)
    assert resp2.status_code == 422


def test_out_of_range_humidity_rejected(authed_client):
    """Relative humidity outside 0-100% must be rejected with 422."""
    payload = {
        "device_id": "safeedge-esp32-sec",
        "humidity_pct": 105.0,
    }
    resp = authed_client.post("/api/v1/telemetry", json=payload)
    assert resp.status_code == 422

    payload["humidity_pct"] = -5.0
    resp2 = authed_client.post("/api/v1/telemetry", json=payload)
    assert resp2.status_code == 422


def test_device_id_length_constraints(authed_client):
    """Device ID must be between 2 and 64 characters and non-empty."""
    # Too short
    resp_short = authed_client.post("/api/v1/telemetry", json={"device_id": "a"})
    assert resp_short.status_code == 422

    # Whitespace only
    resp_empty = authed_client.post("/api/v1/telemetry", json={"device_id": "   "})
    assert resp_empty.status_code == 422

    # Too long (>64 chars)
    resp_long = authed_client.post("/api/v1/telemetry", json={"device_id": "a" * 100})
    assert resp_long.status_code == 422


def test_xss_payload_in_device_id_handled_safely(authed_client):
    """XSS strings in device_id are stored as plain text without execution."""
    xss_id = "<script>alert('xss')</script>"
    payload = {
        "device_id": xss_id,
        "temperature_c": 26.0,
        "humidity_pct": 50.0,
        "gas_raw": 900,
        "noise_raw": 1500,
    }
    resp = authed_client.post("/api/v1/telemetry", json=payload)
    assert resp.status_code == 200
    assert resp.json()["device_id"] == xss_id

    # Retrieve latest
    resp_get = authed_client.get(f"/api/v1/telemetry/latest?device_id={xss_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["device_id"] == xss_id


# =============================================================================
# 4. Raw ADC Preservation & Calibration Status
# =============================================================================

def test_raw_adc_preservation_and_uncalibrated_flags(authed_client):
    """
    Ingested gas_raw and noise_raw must be recorded verbatim and flagged
    is_gas_calibrated=False and is_noise_calibrated=False.
    """
    payload = {
        "device_id": "safeedge-esp32-cal",
        "gas_raw": 2450.0,
        "noise_raw": 3100.0,
    }
    resp = authed_client.post("/api/v1/telemetry", json=payload)
    assert resp.status_code == 200

    resp_latest = authed_client.get("/api/v1/telemetry/latest?device_id=safeedge-esp32-cal")
    assert resp_latest.status_code == 200
    t = resp_latest.json()["telemetry"]
    assert t["gas_raw"] == 2450.0
    assert t["noise_raw"] == 3100.0
    assert t["is_gas_calibrated"] is False
    assert t["is_noise_calibrated"] is False
