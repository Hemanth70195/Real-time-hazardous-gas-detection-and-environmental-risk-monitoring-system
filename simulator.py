# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard — Industrial IoT Hardware & Telemetry Simulator.
Provides real-time simulated sensor readings, threshold evaluations,
and hardware node telemetry for the industrial monitoring dashboard.

Designed so read_sensors() can easily be swapped with real serial or
MQTT hardware drivers without altering UI code.
"""

import json
import math
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.serial_sensor_receiver import get_serial_receiver

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "environmental_thresholds.json"

# Hardware Sensor Nodes definition
SENSOR_NODES = [
    {"node": "GAS-01", "sensor": "MQ-135", "rssi": "-48 dBm", "batt": "92%", "state": "Online"},
    {"node": "DHT-02", "sensor": "DHT22", "rssi": "-52 dBm", "batt": "88%", "state": "Online"},
    {"node": "MIC-04", "sensor": "Sound level", "rssi": "-55 dBm", "batt": "81%", "state": "Online"},
]

# Baseline parameter definitions matching the reference mockup
DEFAULT_PARAMETERS = {
    "temperature": {
        "name": "Temperature",
        "unit": "°C",
        "node": "DHT-02",
        "sensor": "DHT22",
        "default": 24.0,
        "min": 0.0,
        "max": 50.0,
        "warn": 35.0,
        "danger": 45.0,
        "drift": 0.3,
        "icon": "thermometer",
    },
    "humidity": {
        "name": "Humidity",
        "unit": "%",
        "node": "DHT-02",
        "sensor": "DHT22",
        "default": 45.0,
        "min": 0.0,
        "max": 100.0,
        "warn": 70.0,
        "danger": 85.0,
        "drift": 0.6,
        "icon": "droplet",
    },
    "noise": {
        "name": "Noise level",
        "unit": "dB",
        "node": "MIC-04",
        "sensor": "Sound level",
        "default": 65.0,
        "min": 40.0,
        "max": 110.0,
        "warn": 85.0,
        "danger": 100.0,
        "drift": 1.2,
        "icon": "volume",
    },
    "gas": {
        "name": "Gas concentration",
        "unit": "ppm",
        "node": "GAS-01",
        "sensor": "MQ-135",
        "default": 8.0,
        "min": 0.0,
        "max": 60.0,
        "warn": 25.0,
        "danger": 50.0,
        "drift": 0.4,
        "icon": "flask",
    },
}

# Demo Scenario Presets
SCENARIOS = {
    "All Safe": {
        "temperature": 24.0,
        "humidity": 45.0,
        "noise": 65.0,
        "gas": 8.0,
        "description": "All monitored parameters well within standard occupational safe zones.",
    },
    "Acoustic Noise Stress": {
        "temperature": 27.5,
        "humidity": 42.0,
        "noise": 88.0,   # Warning
        "gas": 12.0,
        "description": "High acoustic sound pressure from active excavation and heavy equipment.",
    },
    "Gas Leak Danger": {
        "temperature": 24.0,
        "humidity": 45.0,
        "noise": 67.0,
        "gas": 58.0,    # Danger
        "description": "Critical toxic/combustible VOC vapor accumulation exceeding evacuation limits.",
    },
    "Heat Stress": {
        "temperature": 46.5,  # Danger
        "humidity": 78.0,   # Warning
        "noise": 62.0,
        "gas": 6.0,
        "description": "Extreme ambient dry-bulb heat combined with high relative humidity.",
    },
    "Multi-Hazard": {
        "temperature": 37.0,  # Warning
        "humidity": 82.0,   # Warning
        "noise": 94.0,   # Warning
        "gas": 52.0,    # Danger
        "description": "Compounded emergency: extreme ambient heat stress and critical toxic gas leakage.",
    },
    "Reset": {
        "temperature": 24.0,
        "humidity": 45.0,
        "noise": 65.0,
        "gas": 8.0,
        "description": "Default baseline initialization values.",
    },
}


class IoTHardwareSimulator:
    """
    Simulates physical IoT hardware telemetry stream with realistic random walk,
    noise perturbations, and threshold monitoring.
    """

    def __init__(self, config_file: Path = CONFIG_PATH):
        self.config_path = config_file
        self.params_spec = DEFAULT_PARAMETERS
        self.current_values: Dict[str, float] = {
            k: spec["default"] for k, spec in self.params_spec.items()
        }
        self.override_active = False
        self.override_values: Dict[str, float] = {}
        self.last_read_time = time.time()
        self.tick = 0
        self.data_source: str = "simulation" 

    def set_override(self, overrides: Dict[str, float]):
        """Sets manual or scenario override values."""
        self.override_active = True
        self.override_values.update(overrides)
        for k, v in overrides.items():
            if k in self.current_values:
                self.current_values[k] = float(v)

    def clear_override(self):
        """Clears manual overrides and returns to live IoT feed."""
        self.override_active = False
        self.override_values.clear()

    def set_data_source(self, mode: str) -> None:
        """Sets active data source mode: 'simulation', 'live_esp32', or 'cloud_esp32'."""
        if mode in ("simulation", "live_esp32", "cloud_esp32"):
            self.data_source = mode

    def evaluate_status(self, key: str, value: float) -> str:
        """Evaluates whether a value is SAFE, WARNING, or DANGER."""
        spec = self.params_spec[key]
        warn = spec["warn"]
        danger = spec["danger"]

        if value >= danger:
            return "DANGER"
        elif value >= warn:
            return "WARNING"
        return "SAFE"

    def read_sensors(self, data_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Primary interface method. Returns a snapshot of current telemetry.
        Supports both 'simulation' (default) and 'live_esp32' (USB Serial).
        """
        active_source = data_source or self.data_source

        # ---------------------------------------------------------------------
        # 0. CLOUD LIVE MODE (ESP32 CLOUD STREAMING VIA REST/MQTT BACKEND)
        # ---------------------------------------------------------------------
        if active_source == "cloud_esp32":
            from core.cloud_sensor_receiver import get_cloud_receiver
            return get_cloud_receiver().fetch_latest_telemetry()

        # ---------------------------------------------------------------------
        # 1. LIVE HARDWARE MODE (ESP32 USB SERIAL)
        # ---------------------------------------------------------------------
        if active_source == "live_esp32":
            receiver = get_serial_receiver()
            is_conn = receiver.is_connected()
            is_stale = receiver.is_data_stale()
            esp32_data = receiver.get_latest_reading()
            status_info = receiver.get_status()

            # If disconnected or stale, do NOT silently fall back to simulation
            if not is_conn or is_stale or esp32_data is None:
                return {
                    "data_source": "live_esp32",
                    "device_id": status_info.get("device_id") or "safeedge-esp32",
                    "is_connected": is_conn,
                    "is_stale": True,
                    "serial_status": status_info,
                    "readings": None,
                    "site_status": "warning",
                    "danger_count": 0,
                    "warning_count": 1,
                    "safe_count": 0,
                    "uncalibrated_count": 0,
                    "total_count": len(self.params_spec),
                    "recommended_action": {
                        "headline": "SENSOR DATA UNAVAILABLE: Connect ESP32 USB serial or switch to Simulation Mode.",
                        "guidelines_warning": "Warning: verify USB cable, selected COM port, and 115200 baud rate.",
                        "guidelines_danger": "Danger: do not assume atmospheric conditions are safe without active data.",
                        "status": "warning",
                    },
                    "timestamp": datetime.now(),
                    "nodes": SENSOR_NODES,
                    "extra_measurements": {},
                }

            # Map validated live ESP32 fields
            # Temperature (°C)
            if esp32_data.temperature_c is not None:
                t_val = round(esp32_data.temperature_c, 1)
                t_status = self.evaluate_status("temperature", t_val)
            else:
                t_val = None
                t_status = "OFFLINE"

            # Humidity (%)
            if esp32_data.humidity_pct is not None:
                h_val = round(esp32_data.humidity_pct, 1)
                h_status = self.evaluate_status("humidity", h_val)
            else:
                h_val = None
                h_status = "OFFLINE"

            # Gas: Raw MQ-135 ADC count (RAW UNCALIBRATED - never convert to ppm without calibration)
            if esp32_data.gas_raw is not None:
                gas_raw_val = round(esp32_data.gas_raw, 0)
                gas_status = "UNCALIBRATED"
            else:
                gas_raw_val = None
                gas_status = "OFFLINE"

            # Noise: Raw Microphone ADC count (RAW UNCALIBRATED - never convert to dB without calibration)
            if esp32_data.noise_raw is not None:
                noise_raw_val = round(esp32_data.noise_raw, 0)
                noise_status = "UNCALIBRATED"
            else:
                noise_raw_val = None
                noise_status = "OFFLINE"

            readings = {
                "temperature": {
                    "key": "temperature",
                    "name": "Temperature",
                    "value": t_val,
                    "unit": "°C",
                    "node": "DHT-02",
                    "sensor": "DHT22 (USB Serial)",
                    "status": t_status,
                    "min": 0.0,
                    "max": 50.0,
                    "warn": self.params_spec["temperature"]["warn"],
                    "danger": self.params_spec["temperature"]["danger"],
                    "icon": "thermometer",
                    "is_uncalibrated": False,
                },
                "humidity": {
                    "key": "humidity",
                    "name": "Humidity",
                    "value": h_val,
                    "unit": "%",
                    "node": "DHT-02",
                    "sensor": "DHT22 (USB Serial)",
                    "status": h_status,
                    "min": 0.0,
                    "max": 100.0,
                    "warn": self.params_spec["humidity"]["warn"],
                    "danger": self.params_spec["humidity"]["danger"],
                    "icon": "droplet",
                    "is_uncalibrated": False,
                },
                "noise": {
                    "key": "noise",
                    "name": "Noise (Raw Microphone)",
                    "value": noise_raw_val,
                    "unit": "ADC",
                    "node": "MIC-04",
                    "sensor": "Sound ADC (Uncalibrated)",
                    "status": noise_status,
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
                    "value": gas_raw_val,
                    "unit": "ADC",
                    "node": "GAS-01",
                    "sensor": "MQ-135 (Uncalibrated)",
                    "status": gas_status,
                    "min": 0.0,
                    "max": 4095.0,
                    "warn": 0.0,
                    "danger": 4095.0,
                    "icon": "flask",
                    "is_uncalibrated": True,
                },
            }

            # Counts across calibrated parameters (do not classify uncalibrated raw values as safe!)
            calibrated_statuses = [t_status, h_status]
            danger_count = sum(1 for s in calibrated_statuses if s == "DANGER")
            warning_count = sum(1 for s in calibrated_statuses if s == "WARNING")
            safe_count = sum(1 for s in calibrated_statuses if s == "SAFE")
            uncalibrated_count = sum(1 for s in [gas_status, noise_status] if s == "UNCALIBRATED")

            if danger_count > 0:
                site_status = "critical"
            elif warning_count > 0:
                site_status = "warning"
            else:
                site_status = "normal"

            # Recommended action
            rec_action = self._determine_recommended_action(readings, site_status)
            # Add note about uncalibrated raw channels
            rec_action["guidelines_warning"] = (
                "Notice: MQ-135 Gas & Sound ADC values are raw uncalibrated readings. "
                "Use certified portable gas detector & sound meter for compliance verification."
            )

            live_nodes = [
                {"node": "GAS-01", "sensor": "MQ-135 (Raw ADC)", "rssi": "USB Serial", "batt": "Line", "state": "Online"},
                {"node": "DHT-02", "sensor": "DHT22 (Calibrated)", "rssi": "USB Serial", "batt": "Line", "state": "Online"},
                {"node": "PM-03", "sensor": "PMS5003 (PM1/2.5/10)", "rssi": "USB Serial", "batt": "Line", "state": "Online"},
                {"node": "MIC-04", "sensor": "Sound (Raw ADC)", "rssi": "USB Serial", "batt": "Line", "state": "Online"},
            ]

            return {
                "readings": readings,
                "site_status": site_status,
                "danger_count": danger_count,
                "warning_count": warning_count,
                "safe_count": safe_count,
                "uncalibrated_count": uncalibrated_count,
                "total_count": len(self.params_spec),
                "recommended_action": rec_action,
                "timestamp": esp32_data.timestamp,
                "data_source": "live_esp32",
                "device_id": esp32_data.device_id,
                "is_stale": False,
                "serial_status": status_info,
                "nodes": live_nodes,
                "extra_measurements": {
                    "pm1_0": esp32_data.pm1_0,
                    "pm2_5": esp32_data.pm2_5,
                    "pm10": esp32_data.pm10,
                    "gas_raw": esp32_data.gas_raw,
                    "noise_raw": esp32_data.noise_raw,
                },
            }

        # ---------------------------------------------------------------------
        # 2. SIMULATION MODE (BOUNDED RANDOM WALK & SCENARIO OVERRIDES)
        # ---------------------------------------------------------------------
        now = time.time()
        elapsed = now - self.last_read_time
        self.last_read_time = now
        self.tick += 1

        readings: Dict[str, Any] = {}
        danger_count = 0
        warning_count = 0
        safe_count = 0

        for key, spec in self.params_spec.items():
            if self.override_active and key in self.override_values:
                val = float(self.override_values[key])
            else:
                # Realistic random walk with small noise
                cur = self.current_values[key]
                drift_max = spec["drift"]
                step = random.uniform(-drift_max, drift_max)
                # Occasional micro-spike (1 in 30 chance)
                if random.random() < 0.03:
                    step += random.uniform(-drift_max * 2, drift_max * 2)

                val = cur + step
                # Keep strictly inside configured min/max bounds
                val = max(spec["min"], min(spec["max"], val))
                self.current_values[key] = val

            status = self.evaluate_status(key, val)
            if status == "DANGER":
                danger_count += 1
            elif status == "WARNING":
                warning_count += 1
            else:
                safe_count += 1

            readings[key] = {
                "key": key,
                "name": spec["name"],
                "value": round(val, 1),
                "unit": spec["unit"],
                "node": spec["node"],
                "sensor": spec["sensor"],
                "status": status,
                "min": spec["min"],
                "max": spec["max"],
                "warn": spec["warn"],
                "danger": spec["danger"],
                "icon": spec["icon"],
                "is_uncalibrated": False,
            }

        # Overall site status aggregation
        if danger_count > 0:
            site_status = "critical"
        elif warning_count > 0:
            site_status = "warning"
        else:
            site_status = "normal"

        # Formulate recommended action based on active severity
        recommended_action = self._determine_recommended_action(readings, site_status)

        return {
            "readings": readings,
            "site_status": site_status,
            "danger_count": danger_count,
            "warning_count": warning_count,
            "safe_count": safe_count,
            "uncalibrated_count": 0,
            "total_count": len(self.params_spec),
            "recommended_action": recommended_action,
            "timestamp": datetime.now(),
            "nodes": SENSOR_NODES,
            "data_source": "simulation",
            "device_id": "simulated-node",
            "is_stale": False,
        }

    def _determine_recommended_action(
        self, readings: Dict[str, Any], site_status: str
    ) -> Dict[str, str]:
        """Provides the active recommendation headline and guidelines."""
        if site_status == "normal":
            return {
                "headline": "No intervention required. Maintain routine site vigilance.",
                "guidelines_warning": "Warning: respirators and exhaust.",
                "guidelines_danger": "Danger: evacuate, SCBA.",
                "status": "normal",
            }
        elif site_status == "critical":
            # Priority: Gas > Dust > Heat > Noise
            if readings["gas"]["status"] == "DANGER":
                headline = "CRITICAL GAS HAZARD: Evacuate zone immediately. Deploy SCBA teams."

            elif readings["temperature"]["status"] == "DANGER":
                headline = "HEAT STRESS EMERGENCY: Mandatory work cessation and thermal cooling protocol."
            elif readings["noise"]["status"] == "DANGER":
                headline = "HAZARDOUS NOISE EXPOSURE: Mandate dual hearing protection or acoustic shutdown."
            else:
                headline = "CRITICAL HAZARD DETECTED: Implement emergency containment measures immediately."
            return {
                "headline": headline,
                "guidelines_warning": "Warning: respirators and exhaust.",
                "guidelines_danger": "Danger: evacuate, SCBA.",
                "status": "critical",
            }
        else:  # Warning
            if readings["gas"]["status"] == "WARNING":
                headline = "ELEVATED GAS WARNING: Deploy vapor respirators and activate forced air exhaust."

            elif readings["noise"]["status"] == "WARNING":
                headline = "ELEVATED NOISE: Mandate certified earplugs/earmuffs in mechanical zone."
            elif readings["temperature"]["status"] == "WARNING":
                headline = "THERMAL WARNING: Institute scheduled shade and hydration breaks."
            elif readings["humidity"]["status"] == "WARNING":
                headline = "HUMIDITY WARNING: Adjust ventilation rates and monitor physiological fatigue."
            else:
                headline = "PRECAUTIONARY ACTION: Elevated reading detected. Verify localized controls."
            return {
                "headline": headline,
                "guidelines_warning": "Warning: respirators and exhaust.",
                "guidelines_danger": "Danger: evacuate, SCBA.",
                "status": "warning",
            }


# Singleton instance helper
_simulator_instance: Optional[IoTHardwareSimulator] = None

def get_simulator() -> IoTHardwareSimulator:
    """Returns the persistent simulator instance."""
    global _simulator_instance
    if _simulator_instance is None:
        _simulator_instance = IoTHardwareSimulator()
    return _simulator_instance

def read_sensors() -> Dict[str, Any]:
    """Convenience top-level function for reading hardware sensors."""
    return get_simulator().read_sensors()
