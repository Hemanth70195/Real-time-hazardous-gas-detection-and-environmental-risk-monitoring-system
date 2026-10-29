"""
SafeEdge HazardGuard - Environmental & Hazardous Gas Safety Core Modules.
"""

from .environmental_simulator import (
    EnvironmentalSimulator,
    HazardStatus,
    EnvironmentalReading,
    EnvironmentalConfigError,
    SIMULATED_DATA_DISCLAIMER_SHORT,
)
from .hazard_assessment import (
    HazardAssessmentEngine,
    HazardAssessment,
    SiteHazardAssessment,
)
from .environmental_dashboard import (
    render_environmental_dashboard,
    render_simulator_view,
    render_history_reports_view,
)
from .hazard_history import (
    HazardEvent,
    HazardHistoryTracker,
)
from .serial_sensor_receiver import (
    SerialSensorReceiver,
    SerialConnectionStatus,
    ESP32ParsedData,
    get_serial_receiver,
)
from .cloud_sensor_receiver import (
    CloudSensorReceiver,
    get_cloud_receiver,
)

__all__ = [
    "EnvironmentalSimulator",
    "HazardStatus",
    "EnvironmentalReading",
    "EnvironmentalConfigError",
    "SIMULATED_DATA_DISCLAIMER_SHORT",
    "HazardAssessmentEngine",
    "HazardAssessment",
    "SiteHazardAssessment",
    "HazardEvent",
    "HazardHistoryTracker",
    "render_environmental_dashboard",
    "render_simulator_view",
    "render_history_reports_view",
    "SerialSensorReceiver",
    "SerialConnectionStatus",
    "ESP32ParsedData",
    "get_serial_receiver",
    "CloudSensorReceiver",
    "get_cloud_receiver",
]
