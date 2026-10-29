# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Cloud IoT FastAPI Backend Ingestion & Dashboard API (Phase 3).
Provides secure HTTPS ingestion for ESP32 devices, real-time telemetry endpoints,
and database persistence for remote multi-site dashboard monitoring.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Security, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.config import (
    CORS_ORIGINS,
    REQUIRE_API_KEY,
    SAFEEDGE_API_KEY,
    STALE_TIMEOUT_SECONDS,
)
from backend.database import get_db, init_db
from backend.models import TelemetryReading, utc_now
from backend.mqtt_worker import get_mqtt_worker
from backend.schemas import (
    DeviceResponse,
    IngestResult,
    LatestTelemetryResponse,
    TelemetryIngestPayload,
    TelemetryResponse,
)
from backend.service import (
    get_all_devices,
    get_device_history,
    get_latest_telemetry_for_device,
    process_and_store_telemetry,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database tables on startup and starts MQTT worker if configured."""
    init_db()
    # Optionally start MQTT background listener
    worker = get_mqtt_worker()
    worker.start()
    yield
    worker.stop()


app = FastAPI(
    title="SafeEdge HazardGuard Cloud IoT API",
    description="Secure telemetry ingestion, persistent storage, and dashboard streaming API for hazardous gas monitoring.",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS middleware for web / dashboard consumption
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> bool:
    """Verifies API key header for protected ingestion and query endpoints."""
    if not REQUIRE_API_KEY:
        return True
    if not x_api_key or x_api_key != SAFEEDGE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key authentication header.",
        )
    return True


# =============================================================================
# 1. System Health & Diagnostics
# =============================================================================

@app.get("/", tags=["Diagnostics"])
def root():
    """Root entrypoint returning service metadata and API documentation links."""
    return {
        "service": "SafeEdge HazardGuard Cloud IoT Backend",
        "version": "3.0.0",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
        "api_v1": "/api/v1",
    }


@app.get("/health", tags=["Diagnostics"])
@app.get("/api/v1/health", tags=["Diagnostics"])
def health_check(db: Session = Depends(get_db)):
    """System health diagnostics: verifies database connectivity and MQTT worker status."""
    db_status = "connected"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    mqtt_status = get_mqtt_worker().get_status()
    is_healthy = "unhealthy" not in db_status

    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": "SafeEdge HazardGuard Cloud Backend",
        "version": "3.0.0",
        "timestamp": utc_now().isoformat(),
        "database": db_status,
        "mqtt_bridge": mqtt_status,
    }


# =============================================================================
# 2. Secure HTTPS Ingestion Endpoint (ESP32 Direct or Gateway)
# =============================================================================

@app.post("/api/v1/telemetry", response_model=IngestResult, tags=["Ingestion"])
def ingest_telemetry(
    payload: TelemetryIngestPayload,
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_api_key),
):
    """
    Ingests validated sensor telemetry from ESP32 over HTTPS:
    - Associates with device ID.
    - Records server timestamp.
    - Validates data ranges.
    - Preserves uncalibrated raw status for MQ-135 and microphone.
    """
    reading = process_and_store_telemetry(
        db=db,
        payload=payload,
        data_source="cloud_https",
    )
    return IngestResult(
        message="Telemetry ingested successfully",
        device_id=reading.device_id,
        reading_id=reading.id,
        server_timestamp=reading.server_timestamp.isoformat(),
    )


# =============================================================================
# 3. Dashboard Real-Time Telemetry & Hazard Evaluation
# =============================================================================

@app.get("/api/v1/telemetry/latest", response_model=LatestTelemetryResponse, tags=["Dashboard"])
def get_latest_telemetry(
    device_id: str = Query(..., description="Target ESP32 device ID, e.g. safeedge-esp32-01"),
    stale_threshold_seconds: Optional[float] = Query(None, description="Custom stale threshold in seconds"),
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_api_key),
):
    """
    Returns the most recent reading, connection state, data freshness flag,
    and computed Hazard Assessment for the dashboard.
    """
    timeout = stale_threshold_seconds if stale_threshold_seconds is not None else STALE_TIMEOUT_SECONDS
    res = get_latest_telemetry_for_device(
        db=db,
        device_id=device_id,
        stale_timeout=timeout,
    )
    return res


@app.get("/api/v1/telemetry/history", response_model=List[TelemetryResponse], tags=["Dashboard"])
def get_telemetry_history(
    device_id: str = Query(..., description="Target ESP32 device ID"),
    limit: int = Query(60, ge=1, le=500, description="Max readings to return"),
    hours: Optional[float] = Query(None, description="Time window in hours"),
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_api_key),
):
    """
    Returns time-series historical telemetry for a device, ordered ascending by time,
    ready for plotting in Streamlit Plotly charts and CSV exports.
    """
    records = get_device_history(db=db, device_id=device_id, limit=limit, hours=hours)
    return records


# =============================================================================
# 4. Device Management & Status
# =============================================================================

@app.get("/api/v1/devices", response_model=List[DeviceResponse], tags=["Devices"])
def list_registered_devices(
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_api_key),
):
    """Returns list of registered ESP32 nodes and their current online/stale status."""
    return get_all_devices(db=db, stale_timeout=STALE_TIMEOUT_SECONDS)

