# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Mock ESP32 Telemetry Generator & Test Scenario Suite (Phase 5).
Generates realistic, schema-compliant, or intentionally faulty ESP32 sensor telemetry
for hardware-independent testing of the USB Serial Receiver, MQTT Ingestion Worker,
FastAPI Backend, Hazard Assessment Engine, and Streamlit Dashboard.

Supported Channels (Phase 4 Specification):
- device_id: Unique hardware identifier
- temperature_c: Ambient temperature in °C (DHT22 calibrated, range: -40.0 to 85.0)
- humidity_pct: Relative humidity in % (DHT22 calibrated, range: 0.0 to 100.0)
- gas_raw: Raw MQ-135 ADC count (uncalibrated 12-bit ADC: 0 to 4095)
- noise_raw: Raw MAX9814 microphone peak-to-peak ADC count (uncalibrated 12-bit ADC: 0 to 4095)
- uptime_ms: Optional device uptime counter in milliseconds

All generated telemetry packets are explicitly tagged and metadata-documented
as SIMULATED TEST DATA.
"""

import json
import random
import time
from typing import Any, Dict, Iterator, List, Optional


class MockESP32TelemetryGenerator:
    """
    Configurable telemetry packet generator covering normal operations,
    environmental spikes, malformed payloads, out-of-bounds conditions,
    sensor disconnections, and delayed/intermittent delivery.
    """

    def __init__(self, device_id: str = "safeedge-esp32-01"):
        self.device_id = device_id
        self._uptime_ms = 1000
        self._gas_baseline = 1200
        self._noise_baseline = 1800

    def _tick_uptime(self, step_ms: int = 2000) -> int:
        self._uptime_ms += step_ms
        return self._uptime_ms

    # =========================================================================
    # 1. Realistic Operational Scenarios
    # =========================================================================

    def generate_normal(self, temp_range=(21.0, 26.0), hum_range=(45.0, 55.0)) -> Dict[str, Any]:
        """Generates nominal, safe environmental readings with subtle sensor noise."""
        return {
            "device_id": self.device_id,
            "temperature_c": round(random.uniform(*temp_range), 1),
            "humidity_pct": round(random.uniform(*hum_range), 1),
            "gas_raw": max(200, min(3500, int(random.gauss(self._gas_baseline, 40)))),
            "noise_raw": max(200, min(3500, int(random.gauss(self._noise_baseline, 60)))),
            "uptime_ms": self._tick_uptime(),
            "_simulated_test_data": True,
            "_scenario": "NORMAL_OPERATION",
        }

    def generate_high_temperature(self, temp: float = 38.5) -> Dict[str, Any]:
        """Generates elevated temperature triggering heat-stress warnings."""
        payload = self.generate_normal()
        payload["temperature_c"] = temp
        payload["_scenario"] = "HIGH_TEMPERATURE"
        return payload

    def generate_low_humidity(self, hum: float = 18.0) -> Dict[str, Any]:
        """Generates dry condition triggering low-humidity warnings."""
        payload = self.generate_normal()
        payload["humidity_pct"] = hum
        payload["_scenario"] = "LOW_HUMIDITY"
        return payload

    def generate_high_humidity(self, hum: float = 88.0) -> Dict[str, Any]:
        """Generates high relative humidity triggering condensation warnings."""
        payload = self.generate_normal()
        payload["humidity_pct"] = hum
        payload["_scenario"] = "HIGH_HUMIDITY"
        return payload

    def generate_gas_spike(self, adc_count: int = 3450) -> Dict[str, Any]:
        """Generates significant raw MQ-135 ADC increase simulating gas accumulation."""
        payload = self.generate_normal()
        payload["gas_raw"] = adc_count
        payload["_scenario"] = "GAS_ANOMALY_RAW_SPIKE"
        return payload

    def generate_noise_spike(self, adc_count: int = 3600) -> Dict[str, Any]:
        """Generates high raw microphone peak-to-peak amplitude simulating acoustic impact."""
        payload = self.generate_normal()
        payload["noise_raw"] = adc_count
        payload["_scenario"] = "ACOUSTIC_NOISE_SPIKE"
        return payload

    # =========================================================================
    # 2. Missing, Null, or Partial Sensor Values
    # =========================================================================

    def generate_missing_sensors(
        self,
        missing_temp: bool = False,
        missing_hum: bool = False,
        missing_gas: bool = False,
        missing_noise: bool = False,
    ) -> Dict[str, Any]:
        """Generates a payload where individual sensors return null (e.g., unplugged or uninitialized)."""
        payload = self.generate_normal()
        if missing_temp:
            payload["temperature_c"] = None
        if missing_hum:
            payload["humidity_pct"] = None
        if missing_gas:
            payload["gas_raw"] = None
        if missing_noise:
            payload["noise_raw"] = None
        payload["_scenario"] = "PARTIAL_SENSOR_DISCONNECTION"
        return payload

    def generate_all_sensors_disconnected(self) -> Dict[str, Any]:
        """Generates a payload where all sensor buses fail simultaneously."""
        return self.generate_missing_sensors(True, True, True, True)

    # =========================================================================
    # 3. Malformed Payloads & Invalid JSON
    # =========================================================================

    def generate_invalid_json(self) -> str:
        """Returns syntactically broken JSON strings that should be safely rejected."""
        broken_variants = [
            '{"device_id": "safeedge-esp32-01", "temperature_c": 25.4,',  # Truncated
            '{"device_id": "safeedge-esp32-01", temperature_c: 25.4}',    # Unquoted key
            'NOT_A_JSON_STRING_DATA_LINE',                                 # Plain text
            '{"device_id": "safeedge-esp32-01", "humidity_pct": %%%}',    # Invalid syntax
            '{"device_id": "safeedge-esp32-01", "gas_raw": undefined}',   # JS undefined
            '{broken-token',                                               # Incomplete brace
            '',                                                            # Empty line
        ]
        return random.choice(broken_variants)

    def generate_malformed_message(self) -> Dict[str, Any]:
        """Returns JSON-valid dictionary with missing mandatory keys or invalid types."""
        malformed_variants = [
            {"wrong_key": 123},                                          # Missing device_id & fields
            {"device_id": "", "temperature_c": 24.0},                    # Empty device_id
            {"device_id": 12345, "temperature_c": 24.0},                 # Non-string device_id
            {"device_id": self.device_id, "temperature_c": "hot"},       # String instead of float
            {"device_id": self.device_id, "humidity_pct": [50.0]},        # Array instead of float
            {"device_id": self.device_id, "gas_raw": {"raw": 1200}},     # Dict instead of number
        ]
        chosen = random.choice(malformed_variants)
        return chosen

    # =========================================================================
    # 4. Out-of-Bounds Physical & ADC Values
    # =========================================================================

    def generate_out_of_range(self) -> Dict[str, Any]:
        """Returns readings that violate physical or 12-bit ADC bounds."""
        out_of_range_variants = [
            {"device_id": self.device_id, "temperature_c": 120.0, "humidity_pct": 50.0, "gas_raw": 1200, "noise_raw": 1800},  # Temp > 85 °C
            {"device_id": self.device_id, "temperature_c": -60.0, "humidity_pct": 50.0, "gas_raw": 1200, "noise_raw": 1800},  # Temp < -40 °C
            {"device_id": self.device_id, "temperature_c": 25.0, "humidity_pct": 140.0, "gas_raw": 1200, "noise_raw": 1800},  # Hum > 100 %
            {"device_id": self.device_id, "temperature_c": 25.0, "humidity_pct": -10.0, "gas_raw": 1200, "noise_raw": 1800},  # Hum < 0 %
            {"device_id": self.device_id, "temperature_c": 25.0, "humidity_pct": 50.0, "gas_raw": -150, "noise_raw": 1800},   # Gas ADC < 0
            {"device_id": self.device_id, "temperature_c": 25.0, "humidity_pct": 50.0, "gas_raw": 5000, "noise_raw": 1800},   # Gas ADC > 4095
            {"device_id": self.device_id, "temperature_c": 25.0, "humidity_pct": 50.0, "gas_raw": 1200, "noise_raw": -50},    # Noise ADC < 0
            {"device_id": self.device_id, "temperature_c": 25.0, "humidity_pct": 50.0, "gas_raw": 1200, "noise_raw": 6000},   # Noise ADC > 4095
        ]
        return random.choice(out_of_range_variants)

    # =========================================================================
    # 5. Complex Sequence Scenarios
    # =========================================================================

    def generate_intermittent_scenario(self, steps: int = 10) -> List[Dict[str, Any]]:
        """
        Simulates intermittent sensor contact (alternating between valid readings and nulls).
        """
        sequence = []
        for i in range(steps):
            if i % 2 == 0:
                pkt = self.generate_normal()
            else:
                # Intermittent DHT or Gas failure
                pkt = self.generate_missing_sensors(missing_temp=True, missing_gas=True)
            sequence.append(pkt)
        return sequence

    def generate_delayed_sequence(self, interval_sec: float = 2.0, delay_step: int = 3) -> List[Dict[str, Any]]:
        """
        Generates packets marked with transmission timestamps, inserting artificial
        gaps to test receiver stale-data detection.
        """
        sequence = []
        curr_time = time.time()
        for i in range(6):
            if i == delay_step:
                # Add gap exceeding stale timeout (e.g. +7 seconds)
                curr_time += 7.0
            else:
                curr_time += interval_sec

            pkt = self.generate_normal()
            pkt["simulated_timestamp"] = curr_time
            sequence.append(pkt)
        return sequence

    def to_serial_line(self, payload: Any) -> str:
        """Formats payload dictionary or invalid string as a newline-delimited serial line."""
        if isinstance(payload, str):
            return payload.strip() + "\n"
        # Filter internal metadata fields for clean transmission test
        clean = {k: v for k, v in payload.items() if not k.startswith("_")}
        return json.dumps(clean) + "\n"
