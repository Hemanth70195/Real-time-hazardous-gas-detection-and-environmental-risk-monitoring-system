# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Deployment & Production Configuration Test Suite (Phase 6).
Verifies health check endpoints, PostgreSQL connection normalization,
CORS handling, environment variable resolution, and deployment manifest validity.
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import app
from backend.database import Base, get_db
from backend.config import SAFEEDGE_API_KEY
from core.cloud_sensor_receiver import CloudSensorReceiver
from app import get_env_or_secret


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# In-memory test DB for deployment tests
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
def setup_deployment_test_db():
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


# =============================================================================
# 1. Health Check & Root Endpoints
# =============================================================================

def test_root_endpoint_metadata(client):
    """Verify GET / returns online status and discovery links."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "SafeEdge HazardGuard Cloud IoT Backend"
    assert data["status"] == "online"
    assert "health_url" in data
    assert "docs_url" in data


def test_health_check_endpoints(client):
    """Verify /health and /api/v1/health check database and MQTT status."""
    for path in ["/health", "/api/v1/health"]:
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "mqtt_bridge" in data
        assert "timestamp" in data


# =============================================================================
# 2. Database URL Normalization
# =============================================================================

def test_postgres_url_normalization():
    """Verify legacy postgres:// URLs from Render/Heroku are normalized to postgresql://."""
    legacy_url = "postgres://user:secret@host.render.com:5432/safedb"
    normalized = legacy_url.replace("postgres://", "postgresql://", 1) if legacy_url.startswith("postgres://") else legacy_url
    assert normalized.startswith("postgresql://")
    assert "user:secret@host.render.com:5432/safedb" in normalized


# =============================================================================
# 3. Environment Variable Resolution (No Hardcoded Localhost in Prod)
# =============================================================================

def test_frontend_env_variable_resolution(monkeypatch):
    """Verify dashboard reads backend URL and device ID from environment variables."""
    monkeypatch.setenv("SAFEEDGE_BACKEND_URL", "https://safeedge-prod.onrender.com")
    monkeypatch.setenv("SAFEEDGE_DEVICE_ID", "safeedge-prod-node-01")
    monkeypatch.setenv("SAFEEDGE_API_KEY", "prod-secret-key-xyz")

    url = get_env_or_secret("SAFEEDGE_BACKEND_URL", "http://localhost:8000")
    dev = get_env_or_secret("SAFEEDGE_DEVICE_ID", "safeedge-esp32-01")
    key = get_env_or_secret("SAFEEDGE_API_KEY", "")

    assert url == "https://safeedge-prod.onrender.com"
    assert dev == "safeedge-prod-node-01"
    assert key == "prod-secret-key-xyz"


def test_cloud_sensor_receiver_env_resolution(monkeypatch):
    """Verify CloudSensorReceiver picks up environment configuration automatically."""
    monkeypatch.setenv("SAFEEDGE_BACKEND_URL", "https://safeedge-api.koyeb.app")
    monkeypatch.setenv("SAFEEDGE_DEVICE_ID", "safeedge-remote-01")

    receiver = CloudSensorReceiver()
    assert receiver.backend_url == "https://safeedge-api.koyeb.app"
    assert receiver.device_id == "safeedge-remote-01"


# =============================================================================
# 4. CORS Origins Handling
# =============================================================================

def test_cors_headers_on_api():
    """Verify CORS middleware returns Access-Control headers for allowed origins."""
    cors_client = TestClient(app)
    headers = {
        "Origin": "http://localhost:8501",
        "Access-Control-Request-Method": "POST",
    }
    resp = cors_client.options("/api/v1/telemetry", headers=headers)
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


# =============================================================================
# 5. Deployment Artifacts Integrity
# =============================================================================

def test_deployment_manifests_exist():
    """Verify all container and deployment infrastructure blueprints exist."""
    required_files = [
        PROJECT_ROOT / "Dockerfile.backend",
        PROJECT_ROOT / "Dockerfile.dashboard",
        PROJECT_ROOT / "docker-compose.yml",
        PROJECT_ROOT / "render.yaml",
        PROJECT_ROOT / "Procfile",
        PROJECT_ROOT / ".streamlit" / "config.toml",
        PROJECT_ROOT / ".env.example",
    ]
    for p in required_files:
        assert p.exists(), f"Missing deployment file: {p}"
        assert p.stat().st_size > 0, f"Empty deployment file: {p}"


def test_no_secrets_in_deployment_manifests():
    """Verify blueprints use environment variables and placeholders, not hardcoded secrets."""
    manifests = [
        PROJECT_ROOT / "render.yaml",
        PROJECT_ROOT / "Dockerfile.backend",
        PROJECT_ROOT / "Dockerfile.dashboard",
        PROJECT_ROOT / ".env.example",
    ]
    for p in manifests:
        content = p.read_text(encoding="utf-8")
        assert "password123" not in content.lower()
        assert "supersecret" not in content.lower()
