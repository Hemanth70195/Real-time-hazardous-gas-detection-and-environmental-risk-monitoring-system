# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Backend Business Logic & Telemetry Service (Phase 3).
Handles telemetry ingestion, database storage, device registry lifecycle,
data freshness evaluation, and integration with the Hazard Assessment engine.
"""

from datetime import datetime, timedelta
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.config import STALE_TIMEOUT_SECONDS
from backend.models import Device, TelemetryReading, utc_now
from backend.schemas import TelemetryIngestPayload
from core.hazard_assessment import HazardAssessmentEngine


def process_and_store_telemetry(
    db: Session,
    payload: TelemetryIngestPayload,
    data_source: str = "cloud_esp32",
    raw_payload_str: Optional[str] = None,
) -> TelemetryReading:
    """
    Ingests and validates incoming telemetry packet:
    1. Upserts the device in the device registry.
    2. Updates last_seen timestamp and marks status as ONLINE.
    3. Persists reading in telemetry_readings with sensor validity flags.
    4. Guarantees raw gas and microphone signals are preserved without ppm/dB conversion.
    """
    now = utc_now()

    # 1. Device registry upsert
    device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    if not device:
        device = Device(
            device_id=payload.device_id,
            display_name=f"ESP32 Node ({payload.device_id})",
            status="ONLINE",
            last_seen=now,
            created_at=now,
        )
        db.add(device)
    else:
        device.last_seen = now
        device.status = "ONLINE"

    # 2. Validity tracking (distinguish missing/fault from legitimate 0.0)
    temp_valid = payload.temperature_c is not None
    hum_valid = payload.humidity_pct is not None
    gas_valid = payload.gas_raw is not None
    noise_valid = payload.noise_raw is not None

    # 3. Create persistent telemetry record
    reading = TelemetryReading(
        device_id=payload.device_id,
        server_timestamp=now,
        device_timestamp=payload.device_timestamp,
        temperature_c=payload.temperature_c,
        humidity_pct=payload.humidity_pct,
        gas_raw=payload.gas_raw,
        noise_raw=payload.noise_raw,
        temp_valid=temp_valid,
        hum_valid=hum_valid,
        gas_valid=gas_valid,
        noise_valid=noise_valid,
        is_gas_calibrated=False,
        is_noise_calibrated=False,
        data_source=data_source,
        raw_payload=raw_payload_str or json.dumps(payload.model_dump()),
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


def get_latest_telemetry_for_device(
    db: Session,
    device_id: str,
    stale_timeout: float = STALE_TIMEOUT_SECONDS,
    config_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retrieves the most recent telemetry reading for a given device,
    computes freshness / stale status, and runs the Hazard Assessment engine.
    """
    now = utc_now()
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return {
            "device_id": device_id,
            "is_connected": False,
            "is_stale": True,
            "status": "NOT_FOUND",
            "last_seen": None,
            "last_seen_seconds_ago": None,
            "telemetry": None,
            "hazard_assessment": None,
        }

    # Calculate data freshness
    elapsed_seconds = (now - device.last_seen).total_seconds() if device.last_seen else 9999.0
    is_stale = elapsed_seconds > stale_timeout
    device_status = "STALE" if is_stale else "ONLINE"
    device.status = device_status

    latest_reading = (
        db.query(TelemetryReading)
        .filter(TelemetryReading.device_id == device_id)
        .order_by(desc(TelemetryReading.server_timestamp))
        .first()
    )

    # Hazard assessment integration
    assessment_dict = None
    if latest_reading and not is_stale:
        meta = config_meta or {
            "temperature": {"display_name": "Temperature", "unit": "°C", "thresholds": {"safe_min": 15, "safe_max": 30, "warning_min": 5, "warning_max": 38}},
            "humidity": {"display_name": "Humidity", "unit": "%", "thresholds": {"safe_min": 30, "safe_max": 60, "warning_min": 20, "warning_max": 80}},
            "gas": {"display_name": "Gas Concentration", "unit": "ppm"},
            "noise": {"display_name": "Noise Level", "unit": "dB"},
        }
        assessment = HazardAssessmentEngine.assess_esp32_reading(latest_reading, meta)
        assessment_dict = assessment.to_dict()

    return {
        "device_id": device.device_id,
        "is_connected": not is_stale,
        "is_stale": is_stale,
        "status": device_status,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
        "last_seen_seconds_ago": round(elapsed_seconds, 1),
        "telemetry": latest_reading.to_dict() if latest_reading else None,
        "hazard_assessment": assessment_dict,
    }


def get_device_history(
    db: Session,
    device_id: str,
    limit: int = 100,
    hours: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves time-series historical telemetry for a device, sorted ascending by time.
    """
    query = db.query(TelemetryReading).filter(TelemetryReading.device_id == device_id)
    if hours:
        since = utc_now() - timedelta(hours=hours)
        query = query.filter(TelemetryReading.server_timestamp >= since)

    readings = (
        query.order_by(desc(TelemetryReading.server_timestamp), desc(TelemetryReading.id))
        .limit(limit)
        .all()
    )
    # Return ascending for time series charts
    return [r.to_dict() for r in reversed(readings)]


def get_all_devices(db: Session, stale_timeout: float = STALE_TIMEOUT_SECONDS) -> List[Dict[str, Any]]:
    """Lists all registered devices and recalculates status based on last seen."""
    now = utc_now()
    devices = db.query(Device).all()
    res = []
    for d in devices:
        elapsed = (now - d.last_seen).total_seconds() if d.last_seen else 9999.0
        d.status = "STALE" if elapsed > stale_timeout else "ONLINE"
        d_dict = d.to_dict()
        d_dict["last_seen_seconds_ago"] = round(elapsed, 1)
        res.append(d_dict)
    return res

