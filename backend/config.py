# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Backend Configuration & Environment Settings (Phase 3).
Loads runtime configuration from environment variables with safe defaults.
"""

import os
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Backend Service API Security
SAFEEDGE_API_KEY = os.getenv("SAFEEDGE_API_KEY", "safeedge-dev-api-key-2026")
REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "true").lower() in ("true", "1", "yes")

# Database Connection
DEFAULT_DB_PATH = PROJECT_ROOT / "safeedge_iot.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Telemetry Freshness & Timeout (seconds)
STALE_TIMEOUT_SECONDS = float(os.getenv("STALE_TIMEOUT_SECONDS", "5.0"))

# MQTT Cloud Broker Configuration
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "broker.hivemq.com")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "8883"))
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "true").lower() in ("true", "1", "yes")
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "safeedge-backend-service")
MQTT_TOPIC_SUB = os.getenv("MQTT_TOPIC_SUB", "safeedge/devices/+/telemetry")

# CORS Configuration
CORS_ORIGINS: List[str] = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501").split(",")
    if origin.strip()
]

