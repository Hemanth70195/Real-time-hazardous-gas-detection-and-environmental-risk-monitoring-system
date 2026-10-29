# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - MQTT Telemetry Ingestion Worker (Phase 3).
Subscribes to secure MQTT broker topics (e.g., safeedge/devices/+/telemetry),
parses and validates JSON payloads, and persists telemetry to the database.
"""

import json
import logging
import ssl
import threading
import time
from typing import Optional

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False
    mqtt = None

from backend.config import (
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_CLIENT_ID,
    MQTT_PASSWORD,
    MQTT_TOPIC_SUB,
    MQTT_USE_TLS,
    MQTT_USERNAME,
)
from backend.database import get_db_session
from backend.schemas import TelemetryIngestPayload
from backend.service import process_and_store_telemetry

logger = logging.getLogger("safeedge.mqtt_worker")


class SafeEdgeMQTTWorker:
    """Background MQTT subscriber for ingesting ESP32 cloud telemetry."""

    def __init__(self):
        self._client: Optional[Any] = None
        self._is_running = False
        self._is_connected = False
        self._messages_count = 0
        self._errors_count = 0
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Starts the MQTT worker in a background daemon thread."""
        if not PAHO_AVAILABLE:
            logger.warning("paho-mqtt library not installed. MQTT worker disabled.")
            return False

        with self._lock:
            if self._is_running:
                return True

            try:
                self._client = mqtt.Client(client_id=MQTT_CLIENT_ID)

                if MQTT_USERNAME and MQTT_PASSWORD:
                    self._client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

                if MQTT_USE_TLS and MQTT_BROKER_PORT == 8883:
                    self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)

                self._client.on_connect = self._on_connect
                self._client.on_disconnect = self._on_disconnect
                self._client.on_message = self._on_message

                logger.info(f"Connecting to MQTT broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}...")
                self._client.connect_async(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
                self._client.loop_start()
                self._is_running = True
                return True

            except Exception as e:
                logger.error(f"Failed to start MQTT worker: {e}")
                self._is_running = False
                return False

    def stop(self):
        """Stops the MQTT client cleanly."""
        with self._lock:
            if self._client and self._is_running:
                try:
                    self._client.loop_stop()
                    self._client.disconnect()
                except Exception as e:
                    logger.debug(f"Error disconnecting MQTT: {e}")
                finally:
                    self._is_running = False
                    self._is_connected = False
                    self._client = None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"MQTT Connected successfully. Subscribing to: {MQTT_TOPIC_SUB}")
            self._is_connected = True
            client.subscribe(MQTT_TOPIC_SUB)
        else:
            logger.warning(f"MQTT Connection failed with return code: {rc}")
            self._is_connected = False

    def _on_disconnect(self, client, userdata, rc):
        logger.info(f"MQTT Disconnected (rc={rc})")
        self._is_connected = False

    def _on_message(self, client, userdata, msg):
        """Processes incoming MQTT payload from ESP32."""
        try:
            payload_str = msg.payload.decode("utf-8").strip()
            data = json.loads(payload_str)

            # Validate via Pydantic schema
            payload = TelemetryIngestPayload(**data)

            # Persist to database
            with get_db_session() as db:
                process_and_store_telemetry(
                    db=db,
                    payload=payload,
                    data_source="cloud_mqtt",
                    raw_payload_str=payload_str,
                )

            self._messages_count += 1

        except Exception as e:
            self._errors_count += 1
            logger.warning(f"Failed to process MQTT message on {msg.topic}: {e}")

    def get_status(self):
        return {
            "is_running": self._is_running,
            "is_connected": self._is_connected,
            "broker": f"{MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}",
            "tls_enabled": MQTT_USE_TLS,
            "topic_sub": MQTT_TOPIC_SUB,
            "messages_count": self._messages_count,
            "errors_count": self._errors_count,
        }


# Singleton instance
_mqtt_worker: Optional[SafeEdgeMQTTWorker] = None

def get_mqtt_worker() -> SafeEdgeMQTTWorker:
    global _mqtt_worker
    if _mqtt_worker is None:
        _mqtt_worker = SafeEdgeMQTTWorker()
    return _mqtt_worker

