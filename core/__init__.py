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
]
