# SafeEdge HazardGuard - Construction Site Hazardous Gas & Environmental Safety Monitoring System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![UI](https://img.shields.io/badge/Web%20App-Streamlit-red.svg)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/Tests-All%20Passing-brightgreen.svg)]()

**SafeEdge HazardGuard** is a dedicated, real-time hazardous gas detection and environmental risk monitoring application for construction and industrial work sites.

It provides real-time multi-hazard telemetry simulation, automatic threshold assessments, actionable safety recommendations, historical trend tracking, and multi-format safety audit reports.

---

## 1. Monitored Environmental Hazards

The system continuously tracks five critical environmental parameters with specialized focus on toxic and volatile hazardous gases:

| Parameter | Unit | Baseline (Safe) | Warning () | Danger () | Primary Site Risks |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Hazardous Gas** | ppm | `0.0 - 24.9` | `25.0 - 49.9` | `>= 50.0` | Toxic inhalation, asphyxiation, VOC toxicity, combustion |
| **Respirable Dust** | µg/m³ | `0.0 - 149.9` | `150.0 - 299.9` | `>= 300.0` | Silicosis, PM10 lung irritation, reduced visibility |
| **Ambient Noise** | dBA | `40.0 - 84.9` | `85.0 - 99.9` | `>= 100.0` | Noise-induced hearing loss, communication masking |
| **Temperature** | °C | `15.0 - 34.9` | `35.0 - 39.9` | `>= 40.0` | Heat exhaustion, heat stroke, impaired cognitive response |
| **Relative Humidity** | % | `30.0 - 69.9` | `70.0 - 84.9` | `>= 85.0` | Severe heat index compounding, heavy sweat inefficiency |

---

## 2. Key Modules & Features

- ** Complete Monitoring Cockpit**: Unified real-time dashboard displaying active metric cards, site-wide safety status badge, active risk alerts, interactive telemetry trends, and report export center.
- ** Live Hazard Simulator**:
  - **Manual Control**: Interactive sliders to model any environmental conditions or simulate accident scenarios.
  - **Automatic Drift**: Stochastic physical drift modeling natural environmental fluctuation.
  - **Accident Presets**: One-click test scenarios including *Gas Leak Danger*, *Severe Heat & Noise*, *High Dust Excavation*, and *Normal Baseline*.
- ** Real-Time Assessment Engine**: Automatically evaluates all parameters against safety thresholds and outputs immediate, actionable mitigation guidance (e.g., compulsory SCBA/respirators, ventilation activation, site evacuation).
- ** Historical Telemetry & Trends**: Rolling historical buffer tracking parameter progression with interactive multi-line charts.
- ** State Transition Event Logger**: Captures and deduplicates status escalations (`SAFE -> WARNING -> DANGER`) and recoveries with ISO-8601 timestamps.
- ** Audit Report Generation**: One-click downloads for:
  - Readings History (`CSV`)
  - State Transition Events (`CSV`)
  - Complete Safety Audit Report (`JSON`)

---

## 3. Installation & Setup

### Prerequisites
- Python 3.10+ (Python 3.14 recommended)
- Windows / Linux / macOS

### Quick Start with PowerShell
```powershell
cd "D:\Antigravity\safety from hazardeous gases"

# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Install required dependencies
pip install -r requirements.txt
```

---

## 4. Launching the Application

Run the application using Streamlit:
```powershell
cd "D:\Antigravity\safety from hazardeous gases"
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Or simply run the helper script:
```powershell
.\runme.ps1
```
Open your web browser at: `http://localhost:8501`

---

## 5. Running the Test Suite

Run the complete automated test suite (including unit and integration tests):
```powershell
cd "D:\Antigravity\safety from hazardeous gases"
.\.venv\Scripts\python.exe -m pytest tests -v
```

All 95+ tests will execute and validate:
- Simulator mathematical drift and bounds
- Threshold assessment logic across all severities
- Deduplicated event logging on state transitions
- CSV and JSON report export formatting
- End-to-end integration and preset controls

---

## 6. Simulation Disclaimer

> [!WARNING]
> **SIMULATION MODE - NOT LIVE SENSOR DATA**
> This application is an educational and engineering simulation prototype. Readings are synthetically generated for demonstration and safety training purposes. Do not use as a life-safety critical gas alarm without certified industrial IoT telemetry hardware.
