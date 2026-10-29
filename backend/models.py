# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Cloud IoT Database Models (Phase 3).
SQLAlchemy models for persistent storage of device identity,
timestamped environmental telemetry, sensor validity flags, and data provenance.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now() -> datetime:
    """Returns naive UTC timestamp without timezone offset for database consistency."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Device(Base):
    """
    Registered physical or virtual IoT edge nodes.
    Tracks device metadata, operational status, and last communication timestamp.
    """
    __tablename__ = "devices"

    device_id = Column(String(64), primary_key=True, index=True)
    display_name = Column(String(128), nullable=False)
    firmware_version = Column(String(32), default="2.0.0")
    status = Column(String(32), default="ONLINE", index=True)  # ONLINE, STALE, OFFLINE
    last_seen = Column(DateTime, default=utc_now, index=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    readings = relationship("TelemetryReading", back_populates="device", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "display_name": self.display_name,
            "firmware_version": self.firmware_version,
            "status": self.status,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TelemetryReading(Base):
    """
    Timestamped environmental sensor readings ingested from ESP32 edge nodes.
    Maintains clean separation between calibrated values and raw uncalibrated ADC counts.
    """
    __tablename__ = "telemetry_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("devices.device_id"), nullable=False, index=True)
    server_timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    device_timestamp = Column(String(32), nullable=True)  # Optional edge ISO string

    # Calibrated physical measurements
    temperature_c = Column(Float, nullable=True)     # DHT22: -40 to 85 °C
    humidity_pct = Column(Float, nullable=True)      # DHT22: 0 to 100 %

    # Raw uncalibrated ADC measurements (CRITICAL: NOT ppm or dB)
    gas_raw = Column(Float, nullable=True)           # MQ-135: 0 to 4095 ADC counts
    noise_raw = Column(Float, nullable=True)         # MAX9814: 0 to 4095 ADC counts

    # Validity indicators (distinguish missing/fault from valid zero readings)
    temp_valid = Column(Boolean, default=True)
    hum_valid = Column(Boolean, default=True)
    gas_valid = Column(Boolean, default=True)
    noise_valid = Column(Boolean, default=True)

    # Calibration & Provenance Metadata
    is_gas_calibrated = Column(Boolean, default=False)
    is_noise_calibrated = Column(Boolean, default=False)
    data_source = Column(String(32), default="cloud_esp32", index=True)
    raw_payload = Column(Text, nullable=True)

    # Relationship
    device = relationship("Device", back_populates="readings")

    # Composite Index for high-speed time-series queries filtered by device
    __table_args__ = (
        Index("idx_device_timestamp", "device_id", "server_timestamp"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "server_timestamp": self.server_timestamp.isoformat(),
            "device_timestamp": self.device_timestamp,
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "gas_raw": self.gas_raw,
            "noise_raw": self.noise_raw,
            "temp_valid": self.temp_valid,
            "hum_valid": self.hum_valid,
            "gas_valid": self.gas_valid,
            "noise_valid": self.noise_valid,
            "is_gas_calibrated": self.is_gas_calibrated,
            "is_noise_calibrated": self.is_noise_calibrated,
            "data_source": self.data_source,
        }

