# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Pydantic Request & Response Schemas (Phase 3).
Defines validation models for telemetry ingestion, device management, and dashboard API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class TelemetryIngestPayload(BaseModel):
    """
    Incoming telemetry schema received from ESP32 edge devices.
    Supports nulls for disconnected/faulty sensors without fabrication.
    """
    device_id: str = Field(..., min_length=2, max_length=64, description="Unique edge node identifier")
    temperature_c: Optional[float] = Field(None, ge=-40.0, le=85.0, description="Ambient temperature in °C")
    humidity_pct: Optional[float] = Field(None, ge=0.0, le=100.0, description="Relative humidity in %")
    gas_raw: Optional[float] = Field(None, ge=0.0, le=65535.0, description="Raw MQ-135 ADC count (uncalibrated)")
    noise_raw: Optional[float] = Field(None, ge=0.0, le=65535.0, description="Raw microphone ADC count (uncalibrated)")
    device_timestamp: Optional[str] = Field(None, description="Optional edge device ISO-8601 timestamp")

    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("device_id cannot be empty or whitespace")
        return clean


class TelemetryResponse(BaseModel):
    """Normalized telemetry reading returned to consumers."""
    id: int
    device_id: str
    server_timestamp: str
    device_timestamp: Optional[str] = None
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    gas_raw: Optional[float] = None
    noise_raw: Optional[float] = None
    is_gas_calibrated: bool = False
    is_noise_calibrated: bool = False
    data_source: str = "cloud_esp32"


class LatestTelemetryResponse(BaseModel):
    """Latest reading envelope returned to the SafeEdge dashboard."""
    device_id: str
    is_connected: bool
    is_stale: bool
    last_seen: Optional[str] = None
    last_seen_seconds_ago: Optional[float] = None
    telemetry: Optional[TelemetryResponse] = None
    hazard_assessment: Optional[Dict[str, Any]] = None


class DeviceResponse(BaseModel):
    """Device registry item."""
    device_id: str
    display_name: str
    firmware_version: str
    status: str
    last_seen: Optional[str] = None
    created_at: Optional[str] = None


class IngestResult(BaseModel):
    """Acknowledgement of successful telemetry ingestion."""
    status: str = "success"
    message: str
    device_id: str
    reading_id: int
    server_timestamp: str

