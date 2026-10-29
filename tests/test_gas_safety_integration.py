"""
Integration tests for SafeEdge HazardGuard (Safety from Hazardous Gases & Environmental Hazards).
"""

import pytest
from core.environmental_simulator import EnvironmentalSimulator, HazardStatus
from core.hazard_assessment import HazardAssessmentEngine
from core.hazard_history import HazardHistoryTracker

def test_gas_safety_integration_full_pipeline():
    simulator = EnvironmentalSimulator()
    assert simulator.parameters_meta is not None
    assert "gas" in simulator.get_parameter_keys()
    
    # 1. Normal baseline state
    readings = simulator.get_all_readings()
    assessment = simulator.assess_current_hazards()
    assert assessment.overall_status in [HazardStatus.SAFE, HazardStatus.WARNING]
    
    # 2. Trigger severe hazardous gas leak
    simulator.set_reading("gas", 75.0)
    gas_assessment = simulator.assess_current_hazards()
    gas_eval = gas_assessment.all_assessments["gas"]
    assert gas_eval.status == HazardStatus.DANGER
    assert gas_assessment.overall_status == HazardStatus.DANGER
    actions_text = " ".join(gas_eval.recommended_actions).lower()
    assert "evacuat" in actions_text or "respirat" in actions_text
    
    # 3. Check event recording
    events = simulator.get_history_tracker().events
    assert len(events) >= 1
    assert events[0].parameter_key == "gas"
    assert events[0].severity == HazardStatus.DANGER
    
    # 4. Check reports generation
    csv_readings = simulator.export_readings_csv()
    assert "Gas Concentration (ppm)" in csv_readings
    csv_events = simulator.export_events_csv()
    assert "Gas" in csv_events or "gas" in csv_events
    json_report = simulator.export_json_report_str()
    assert "hazard_events" in json_report

def test_monitored_parameters_present():
    simulator = EnvironmentalSimulator()
    readings = simulator.get_all_readings()
    required_keys = {"temperature", "humidity", "noise", "gas"}
    assert required_keys.issubset(set(readings.keys()))

def test_gas_leak_danger_thresholds():
    simulator = EnvironmentalSimulator()
    simulator.set_reading("gas", 60.0)
    readings = simulator.get_all_readings()
    assert readings["gas"].value >= 50.0
    assessment = simulator.assess_current_hazards()
    assert assessment.all_assessments["gas"].status == HazardStatus.DANGER
