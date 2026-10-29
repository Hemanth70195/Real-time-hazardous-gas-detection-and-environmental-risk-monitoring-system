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

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "environmental_thresholds.json"

# Hardware Sensor Nodes definition
SENSOR_NODES = [
    {"node": "GAS-01", "sensor": "MQ-135", "rssi": "-48 dBm", "batt": "92%", "state": "Online"},
    {"node": "DHT-02", "sensor": "DHT22", "rssi": "-52 dBm", "batt": "88%", "state": "Online"},
    {"node": "PM-03", "sensor": "PMS5003", "rssi": "-61 dBm", "batt": "76%", "state": "Online"},
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
    "dust": {
        "name": "Dust concentration",
        "unit": "µg/m³",
        "node": "PM-03",
        "sensor": "PMS5003",
        "default": 28.0,
        "min": 0.0,
        "max": 250.0,
        "warn": 100.0,
        "danger": 200.0,
        "drift": 2.5,
        "icon": "wind",
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
        "dust": 28.0,
        "noise": 65.0,
        "gas": 8.0,
        "description": "All 5 parameters well within standard occupational safe zones.",
    },
    "Dust & Noise": {
        "temperature": 27.5,
        "humidity": 42.0,
        "dust": 115.0,  # Warning
        "noise": 88.0,   # Warning
        "gas": 12.0,
        "description": "High particulate and acoustic noise from active excavation and grinding.",
    },
    "Gas Leak Danger": {
        "temperature": 24.0,
        "humidity": 45.0,
        "dust": 32.0,
        "noise": 67.0,
        "gas": 58.0,    # Danger
        "description": "Critical toxic/combustible VOC vapor accumulation exceeding evacuation limits.",
    },
    "Heat Stress": {
        "temperature": 46.5,  # Danger
        "humidity": 78.0,   # Warning
        "dust": 24.0,
        "noise": 62.0,
        "gas": 6.0,
        "description": "Extreme ambient dry-bulb heat combined with high relative humidity.",
    },
    "Multi-Hazard": {
        "temperature": 37.0,  # Warning
        "humidity": 82.0,   # Warning
        "dust": 210.0,  # Danger
        "noise": 94.0,   # Warning
        "gas": 52.0,    # Danger
        "description": "Compounded emergency: catastrophic dust explosion risk and gas leakage.",
    },
    "Reset": {
        "temperature": 24.0,
        "humidity": 45.0,
        "dust": 28.0,
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

    def read_sensors(self) -> Dict[str, Any]:
        """
        Primary interface method. Returns a snapshot of current telemetry.
        Can be substituted with a real hardware driver (MQTT, Modbus, Serial)
        without modifying UI components.
        """
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
            "total_count": len(self.params_spec),
            "recommended_action": recommended_action,
            "timestamp": datetime.now(),
            "nodes": SENSOR_NODES,
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
            elif readings["dust"]["status"] == "DANGER":
                headline = "CRITICAL PARTICULATE DANGER: Halt dry operations. Mandate P100 respirators."
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
            elif readings["dust"]["status"] == "WARNING":
                headline = "DUST WARNING: Activate water spray cannons and mandate N95 particulate masks."
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
