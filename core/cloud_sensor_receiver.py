# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Cloud IoT Telemetry Receiver Client (Phase 3).
Connects the Streamlit dashboard to the SafeEdge Cloud Ingestion API
to retrieve real-time streaming telemetry and historical records.
"""

from datetime import datetime
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.hazard_assessment import HazardAssessmentEngine

logger = logging.getLogger("safeedge.cloud_receiver")


class CloudSensorReceiver:
    """
    Client for fetching real-time and historical ESP32 telemetry
    from the SafeEdge Cloud Backend REST API.
    """

    def __init__(
        self,
        backend_url: Optional[str] = None,
        api_key: Optional[str] = None,
        device_id: Optional[str] = None,
        stale_timeout_seconds: Optional[float] = None,
    ):
        raw_url = backend_url or os.getenv("SAFEEDGE_BACKEND_URL", "http://localhost:8000")
        self.backend_url = raw_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("SAFEEDGE_API_KEY", "safeedge-dev-api-key-2026")
        self.device_id = (device_id or os.getenv("SAFEEDGE_DEVICE_ID", "safeedge-esp32-01")).strip()
        timeout = stale_timeout_seconds if stale_timeout_seconds is not None else float(os.getenv("STALE_TIMEOUT_SECONDS", "5.0"))
        self.stale_timeout_seconds = timeout

        self._last_telemetry: Optional[Dict[str, Any]] = None
        self._last_fetch_time: Optional[float] = None
        self._is_connected = False
        self._is_stale = True
        self._last_error: Optional[str] = None
        self._lock = threading.RLock()

    def set_config(
        self,
        backend_url: Optional[str] = None,
        api_key: Optional[str] = None,
        device_id: Optional[str] = None,
        stale_timeout: Optional[float] = None,
    ):
        """Updates connection settings dynamically from dashboard controls."""
        with self._lock:
            if backend_url:
                self.backend_url = backend_url.rstrip("/")
            if api_key is not None:
                self.api_key = api_key
            if device_id:
                self.device_id = device_id.strip()
            if stale_timeout is not None:
                self.stale_timeout_seconds = stale_timeout

    def test_connection(self) -> Tuple[bool, str]:
        """Tests connectivity and health of the cloud backend service."""
        try:
            url = f"{self.backend_url}/api/v1/health"
            headers = {"X-API-Key": self.api_key}
            resp = requests.get(url, headers=headers, timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                return True, f"Connected to Cloud Backend (v{data.get('version', '3.0.0')})"
            elif resp.status_code == 401:
                return False, "Authentication Failed: Invalid API Key."
            else:
                return False, f"Backend returned HTTP {resp.status_code}"
        except Exception as e:
            return False, f"Cannot reach cloud backend: {str(e)}"

    def fetch_latest_telemetry(self) -> Dict[str, Any]:
        """
        Polls the cloud backend for the latest reading for self.device_id.
        Returns a normalized dictionary structured identically to IoTHardwareSimulator.read_sensors().
        """
        with self._lock:
            headers = {"X-API-Key": self.api_key}
            url = f"{self.backend_url}/api/v1/telemetry/latest?device_id={self.device_id}"

            try:
                resp = requests.get(url, headers=headers, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    self._is_connected = data.get("is_connected", False)
                    self._is_stale = data.get("is_stale", True)
                    self._last_error = None
                    self._last_fetch_time = time.time()

                    tel = data.get("telemetry")
                    if not tel or self._is_stale:
                        return self._build_stale_response(data)

                    # Transform valid cloud reading into dashboard structure
                    return self._build_live_cloud_response(data)

                elif resp.status_code == 401:
                    self._is_connected = False
                    self._last_error = "Authentication failed (invalid API key)"
                    return self._build_error_response("Authentication Error: Invalid API key.")
                else:
                    self._is_connected = False
                    self._last_error = f"Backend error HTTP {resp.status_code}"
                    return self._build_error_response(f"HTTP {resp.status_code} from Cloud Backend")

            except Exception as e:
                self._is_connected = False
                self._is_stale = True
                self._last_error = str(e)
                return self._build_error_response(f"Cloud Connection Error: {str(e)}")

    def fetch_history(self, limit: int = 60, hours: Optional[float] = None) -> List[Dict[str, Any]]:
        """Fetches historical readings from the cloud backend database."""
        with self._lock:
            headers = {"X-API-Key": self.api_key}
            url = f"{self.backend_url}/api/v1/telemetry/history?device_id={self.device_id}&limit={limit}"
            if hours:
                url += f"&hours={hours}"

            try:
                resp = requests.get(url, headers=headers, timeout=3.0)
                if resp.status_code == 200:
                    return resp.json()
                return []
            except Exception as e:
                logger.warning(f"Error fetching cloud history: {e}")
                return []

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostic status of the cloud receiver link."""
        with self._lock:
            return {
                "backend_url": self.backend_url,
                "device_id": self.device_id,
                "is_connected": self._is_connected,
                "is_stale": self._is_stale,
                "last_error": self._last_error,
                "last_fetch_time": self._last_fetch_time,
            }

    # -------------------------------------------------------------------------
    # Response Builders
    # -------------------------------------------------------------------------

    def _build_stale_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "data_source": "cloud_esp32",
            "device_id": self.device_id,
            "is_connected": self._is_connected,
            "is_stale": True,
            "readings": None,
            "site_status": "warning",
            "danger_count": 0,
            "warning_count": 1,
            "safe_count": 0,
            "uncalibrated_count": 0,
            "total_count": 4,
            "last_seen": data.get("last_seen"),
            "last_seen_seconds_ago": data.get("last_seen_seconds_ago"),
            "recommended_action": {
                "headline": f"CLOUD TELEMETRY STALE / UNAVAILABLE: No fresh packet from {self.device_id}.",
                "guidelines_warning": "Warning: verify ESP32 Wi-Fi connection and cloud backend ingestion.",
                "guidelines_danger": "Danger: do not assume atmospheric conditions are safe without active data.",
                "status": "warning",
            },
            "timestamp": datetime.now(),
            "nodes": self._build_cloud_nodes(status="Stale"),
        }

    def _build_error_response(self, error_msg: str) -> Dict[str, Any]:
        return {
            "data_source": "cloud_esp32",
            "device_id": self.device_id,
            "is_connected": False,
            "is_stale": True,
            "readings": None,
            "site_status": "warning",
            "danger_count": 0,
            "warning_count": 1,
            "safe_count": 0,
            "uncalibrated_count": 0,
            "total_count": 4,
            "recommended_action": {
                "headline": f"CLOUD BACKEND UNAVAILABLE: {error_msg}",
                "guidelines_warning": "Verify backend service is running (python -m uvicorn backend.app:app).",
                "guidelines_danger": "Check API key, firewall, and network settings.",
                "status": "warning",
            },
            "timestamp": datetime.now(),
            "nodes": self._build_cloud_nodes(status="Offline"),
        }

    def _build_live_cloud_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        tel = data["telemetry"]
        t_raw = tel.get("temperature_c")
        if t_raw is not None:
            t_val = round(float(t_raw), 1)
            t_stat = "DANGER" if t_val >= 45.0 else ("WARNING" if t_val >= 35.0 else "SAFE")
        else:
            t_val = None
            t_stat = "OFFLINE"

        h_raw = tel.get("humidity_pct")
        if h_raw is not None:
            h_val = round(float(h_raw), 1)
            h_stat = "DANGER" if h_val >= 85.0 else ("WARNING" if h_val >= 70.0 else "SAFE")
        else:
            h_val = None
            h_stat = "OFFLINE"

        gas_raw = round(float(tel["gas_raw"]), 0) if tel.get("gas_raw") is not None else None
        gas_stat = "UNCALIBRATED" if gas_raw is not None else "OFFLINE"

        noise_raw = round(float(tel["noise_raw"]), 0) if tel.get("noise_raw") is not None else None
        noise_stat = "UNCALIBRATED" if noise_raw is not None else "OFFLINE"

        readings = {
            "temperature": {
                "key": "temperature",
                "name": "Temperature",
                "value": t_val,
                "unit": "°C",
                "node": "DHT-02",
                "sensor": "DHT22 (Cloud Wi-Fi)",
                "status": t_stat,
                "min": 0.0,
                "max": 50.0,
                "warn": 35.0,
                "danger": 45.0,
                "icon": "thermometer",
                "is_uncalibrated": False,
            },
            "humidity": {
                "key": "humidity",
                "name": "Humidity",
                "value": h_val,
                "unit": "%",
                "node": "DHT-02",
                "sensor": "DHT22 (Cloud Wi-Fi)",
                "status": h_stat,
                "min": 0.0,
                "max": 100.0,
                "warn": 70.0,
                "danger": 85.0,
                "icon": "droplet",
                "is_uncalibrated": False,
            },
            "noise": {
                "key": "noise",
                "name": "Noise (Raw Microphone)",
                "value": noise_raw,
                "unit": "ADC",
                "node": "MIC-04",
                "sensor": "Sound ADC (Uncalibrated)",
                "status": noise_stat,
                "min": 0.0,
                "max": 4095.0,
                "warn": 0.0,
                "danger": 4095.0,
                "icon": "volume",
                "is_uncalibrated": True,
            },
            "gas": {
                "key": "gas",
                "name": "Gas (Raw MQ-135)",
                "value": gas_raw,
                "unit": "ADC",
                "node": "GAS-01",
                "sensor": "MQ-135 (Uncalibrated)",
                "status": gas_stat,
                "min": 0.0,
                "max": 4095.0,
                "warn": 0.0,
                "danger": 4095.0,
                "icon": "flask",
                "is_uncalibrated": True,
            },
        }

        cal_stats = [t_stat, h_stat]
        danger_count = sum(1 for s in cal_stats if s == "DANGER")
        warning_count = sum(1 for s in cal_stats if s == "WARNING")
        safe_count = sum(1 for s in cal_stats if s == "SAFE")

        site_status = "critical" if danger_count > 0 else ("warning" if warning_count > 0 else "normal")

        # Recommended action
        if site_status == "critical":
            headline = "CRITICAL HAZARD DETECTED VIA CLOUD STREAM: Evacuate affected zones immediately."
        elif site_status == "warning":
            headline = "ELEVATED WARNING VIA CLOUD STREAM: Verify local ventilation and protective controls."
        else:
            headline = "Site environmental parameters normal. Continuous cloud streaming active."

        return {
            "readings": readings,
            "site_status": site_status,
            "danger_count": danger_count,
            "warning_count": warning_count,
            "safe_count": safe_count,
            "uncalibrated_count": 2,
            "total_count": 4,
            "recommended_action": {
                "headline": headline,
                "guidelines_warning": "Notice: MQ-135 Gas & Sound ADC values are raw uncalibrated readings.",
                "guidelines_danger": "Danger: evacuate, SCBA.",
                "status": site_status,
            },
            "timestamp": datetime.fromisoformat(tel["server_timestamp"]) if tel.get("server_timestamp") else datetime.now(),
            "data_source": "cloud_esp32",
            "device_id": self.device_id,
            "is_stale": False,
            "last_seen_seconds_ago": data.get("last_seen_seconds_ago"),
            "nodes": self._build_cloud_nodes(status="Online"),
        }

    def _build_cloud_nodes(self, status: str = "Online") -> List[Dict[str, Any]]:
        return [
            {"node": "GAS-01", "sensor": "MQ-135 (Raw ADC)", "rssi": "Cloud Wi-Fi", "batt": "Line", "state": status},
            {"node": "DHT-02", "sensor": "DHT22 (Calibrated)", "rssi": "Cloud Wi-Fi", "batt": "Line", "state": status},
            {"node": "MIC-04", "sensor": "Sound (Raw ADC)", "rssi": "Cloud Wi-Fi", "batt": "Line", "state": status},
        ]


# Singleton instance
_cloud_receiver_instance: Optional[CloudSensorReceiver] = None
_cloud_lock = threading.Lock()

def get_cloud_receiver() -> CloudSensorReceiver:
    global _cloud_receiver_instance
    with _cloud_lock:
        if _cloud_receiver_instance is None:
            _cloud_receiver_instance = CloudSensorReceiver()
        return _cloud_receiver_instance

