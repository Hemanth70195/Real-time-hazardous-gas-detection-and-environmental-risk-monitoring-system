# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Backend Package (Phase 3).
"""

from .config import SAFEEDGE_API_KEY, STALE_TIMEOUT_SECONDS, DATABASE_URL
from .database import get_db, init_db, engine, SessionLocal
from .models import Device, TelemetryReading
from .schemas import TelemetryIngestPayload, LatestTelemetryResponse, TelemetryResponse
from .service import process_and_store_telemetry, get_latest_telemetry_for_device, get_device_history

__all__ = [
    "SAFEEDGE_API_KEY",
    "STALE_TIMEOUT_SECONDS",
    "DATABASE_URL",
    "get_db",
    "init_db",
    "engine",
    "SessionLocal",
    "Device",
    "TelemetryReading",
    "TelemetryIngestPayload",
    "LatestTelemetryResponse",
    "TelemetryResponse",
    "process_and_store_telemetry",
    "get_latest_telemetry_for_device",
    "get_device_history",
]

