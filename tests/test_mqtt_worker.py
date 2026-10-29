# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - MQTT Worker Hardware-Independent Test Suite (Phase 5).
Verifies MQTT cloud telemetry ingestion without requiring an active external broker:
1. Message reception and JSON deserialization.
2. Pydantic schema validation.
3. Database persistence via get_db_session.
4. Handling of malformed, broken, and out-of-range payloads.
5. Graceful handling of broker connection failures, disconnects, and reconnects.
6. Resource cleanup on worker shutdown.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import TelemetryReading, Device
from backend.mqtt_worker import SafeEdgeMQTTWorker


# Isolated in-memory SQLite database for MQTT worker testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_mqtt_test_db(monkeypatch):
    """Initializes tables and monkeypatches get_db_session to use test_engine."""
    Base.metadata.create_all(bind=test_engine)

    from contextlib import contextmanager

    @contextmanager
    def mock_get_db_session():
        session = TestingSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr("backend.mqtt_worker.get_db_session", mock_get_db_session)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def mqtt_worker():
    return SafeEdgeMQTTWorker()


def make_mock_message(topic: str, payload_dict_or_str):
    """Helper to construct a mock paho-mqtt message object."""
    msg = MagicMock()
    msg.topic = topic
    if isinstance(payload_dict_or_str, (dict, list)):
        msg.payload = json.dumps(payload_dict_or_str).encode("utf-8")
    elif isinstance(payload_dict_or_str, str):
        msg.payload = payload_dict_or_str.encode("utf-8")
    else:
        msg.payload = payload_dict_or_str
    return msg


# =============================================================================
# 1. Message Ingestion & Schema Validation
# =============================================================================

def test_mqtt_ingest_valid_phase4_message(mqtt_worker):
    """Verify incoming MQTT message is validated and persisted to database."""
    payload = {
        "device_id": "safeedge-esp32-mqtt",
        "temperature_c": 26.5,
        "humidity_pct": 52.0,
        "gas_raw": 1150.0,
        "noise_raw": 1720.0,
    }
    msg = make_mock_message("safeedge/devices/safeedge-esp32-mqtt/telemetry", payload)
    mqtt_worker._on_message(client=None, userdata=None, msg=msg)

    assert mqtt_worker._messages_count == 1
    assert mqtt_worker._errors_count == 0

    # Verify persisted in database
    db = TestingSessionLocal()
    reading = db.query(TelemetryReading).filter(TelemetryReading.device_id == "safeedge-esp32-mqtt").first()
    assert reading is not None
    assert reading.temperature_c == 26.5
    assert reading.humidity_pct == 52.0
    assert reading.gas_raw == 1150.0
    assert reading.noise_raw == 1720.0
    assert reading.data_source == "cloud_mqtt"
    assert reading.is_gas_calibrated is False
    assert reading.is_noise_calibrated is False
    db.close()


def test_mqtt_ingest_partial_telemetry(mqtt_worker):
    """Verify disconnected sensors (null values) are persisted safely."""
    payload = {
        "device_id": "safeedge-esp32-mqtt",
        "temperature_c": None,
        "humidity_pct": None,
        "gas_raw": 1300.0,
        "noise_raw": 1600.0,
    }
    msg = make_mock_message("safeedge/devices/safeedge-esp32-mqtt/telemetry", payload)
    mqtt_worker._on_message(client=None, userdata=None, msg=msg)

    assert mqtt_worker._messages_count == 1
    assert mqtt_worker._errors_count == 0

    db = TestingSessionLocal()
    reading = db.query(TelemetryReading).filter(TelemetryReading.device_id == "safeedge-esp32-mqtt").first()
    assert reading is not None
    assert reading.temperature_c is None
    assert reading.humidity_pct is None
    assert reading.gas_raw == 1300.0
    db.close()


def test_mqtt_ingest_legacy_dust_fields_ignored(mqtt_worker):
    """Verify backward compatibility: extra dust fields in MQTT message are ignored."""
    payload = {
        "device_id": "safeedge-esp32-mqtt",
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "gas_raw": 1100.0,
        "noise_raw": 1500.0,
        "pm1_0": 10.0,
        "pm2_5": 20.0,
        "pm10": 35.0,
    }
    msg = make_mock_message("safeedge/devices/safeedge-esp32-mqtt/telemetry", payload)
    mqtt_worker._on_message(client=None, userdata=None, msg=msg)

    assert mqtt_worker._messages_count == 1
    assert mqtt_worker._errors_count == 0


def test_mqtt_malformed_json_rejected(mqtt_worker):
    """Verify broken JSON strings increment error counter and do not crash."""
    msg = make_mock_message("safeedge/devices/test/telemetry", "NOT_JSON_DATA_LINE")
    mqtt_worker._on_message(client=None, userdata=None, msg=msg)

    assert mqtt_worker._messages_count == 0
    assert mqtt_worker._errors_count == 1


def test_mqtt_out_of_bounds_payload_rejected(mqtt_worker):
    """Verify impossible physical readings are rejected by Pydantic validation."""
    bad_payload = {
        "device_id": "safeedge-esp32-mqtt",
        "temperature_c": 150.0,  # Invalid: > 85 °C
        "humidity_pct": 50.0,
        "gas_raw": 1200.0,
        "noise_raw": 1500.0,
    }
    msg = make_mock_message("safeedge/devices/safeedge-esp32-mqtt/telemetry", bad_payload)
    mqtt_worker._on_message(client=None, userdata=None, msg=msg)

    assert mqtt_worker._messages_count == 0
    assert mqtt_worker._errors_count == 1


# =============================================================================
# 2. Connection Lifecycle & Error Handling
# =============================================================================

def test_mqtt_connection_callbacks(mqtt_worker):
    """Verify _on_connect and _on_disconnect maintain connection flags."""
    mock_client = MagicMock()

    # Success connect (rc=0)
    mqtt_worker._on_connect(mock_client, None, None, rc=0)
    assert mqtt_worker._is_connected is True
    mock_client.subscribe.assert_called_once()

    # Disconnect
    mqtt_worker._on_disconnect(mock_client, None, rc=1)
    assert mqtt_worker._is_connected is False

    # Failed connect (rc=5: Unauthorized)
    mqtt_worker._on_connect(mock_client, None, None, rc=5)
    assert mqtt_worker._is_connected is False


def test_mqtt_status_reporting(mqtt_worker):
    """Verify get_status returns accurate worker metrics."""
    status = mqtt_worker.get_status()
    assert "is_running" in status
    assert "is_connected" in status
    assert "broker" in status
    assert "messages_count" in status
    assert "errors_count" in status
    assert status["messages_count"] == 0
    assert status["errors_count"] == 0


def test_mqtt_stop_cleanup(mqtt_worker):
    """Verify stop() cleanly closes client and releases resources."""
    mock_client = MagicMock()
    mqtt_worker._client = mock_client
    mqtt_worker._is_running = True
    mqtt_worker._is_connected = True

    mqtt_worker.stop()

    assert mqtt_worker._is_running is False
    assert mqtt_worker._is_connected is False
    assert mqtt_worker._client is None
    mock_client.loop_stop.assert_called_once()
    mock_client.disconnect.assert_called_once()

