# SafeEdge HazardGuard — Comprehensive Final Technical Project Report

**Project Title:** Real-Time Hazardous Gas Detection and Environmental Risk Monitoring System (SafeEdge HazardGuard)  
**Repository:** [GitHub: Hemanth70195/Real-time-hazardous-gas-detection-and-environmental-risk-monitoring-system](https://github.com/Hemanth70195/Real-time-hazardous-gas-detection-and-environmental-risk-monitoring-system)  
**System Version:** 3.0.0 (Production-Ready Architecture)  
**Date:** October 2026  

---

## 1. Executive Summary & Problem Statement

### 1.1 Problem Statement
Industrial facilities, manufacturing plants, and construction work sites are subject to severe occupational hazards arising from toxic and flammable gas accumulations, extreme ambient heat, and excessive acoustic noise. According to statutory guidelines from the Occupational Safety and Health Administration (OSHA 1926/1910) and the National Institute for Occupational Safety and Health (NIOSH), failure to detect hazardous atmospheric changes promptly leads to occupational respiratory illnesses, hearing loss, heat stroke, and catastrophic explosions.

Traditional commercial gas and environmental monitoring systems suffer from three primary shortcomings:
1. **High Procurement and Maintenance Costs**: Specialized multi-gas detectors often cost thousands of dollars per monitoring point, making wide-area spatial coverage cost-prohibitive for small and medium contractors.
2. **Siloed, Disconnected Monitoring**: Standalone handheld detectors alarm only locally without transmitting time-series telemetry to remote safety commanders or centralized control rooms.
3. **Rigid Architecture & Hardware Dependency**: Many software tools require proprietary hardware to be physically plugged in at all times, preventing robust development, offline safety training, and software-in-the-loop stress testing.

### 1.2 The SafeEdge HazardGuard Solution
**SafeEdge HazardGuard** resolves these challenges by introducing a flexible, multi-modal industrial IoT architecture that bridges low-cost edge sensing with cloud-native monitoring and analysis:
- **Tri-Modal Operation**: Seamlessly switches between **Simulation Mode** (for safety drills and training), **Live Hardware Mode (USB Serial)** (for on-site edge debugging), and **Cloud Live Mode (IoT Streaming)** (for wide-area multi-site surveillance).
- **Comprehensive Multi-Hazard Detection**: Continuously monitors 4 environmental parameters: Temperature, Relative Humidity, Ambient Noise, and Hazardous Gas.
- **Dynamic Risk Evaluation & Actionable Protocols**: Employs an automated Hazard Assessment Engine that correlates multi-sensor readings, evaluates exposure thresholds, generates emergency alerts, and displays specific OSHA/NIOSH-aligned protocols (e.g. SCBA deployment, ventilation activation).
- **Cost-Optimized Hardware BOM**: Optimized for affordability by removing redundant, high-cost particulate sensors (PMS5003) while retaining essential hazardous atmospheric sensors (MQ-135, DHT22, MAX9814).

---

## 2. End-to-End System Architecture

The SafeEdge architecture is structured into four decoupled layers: Physical Edge Hardware, Ingestion & Transport, Persistence & Business Logic, and Visualization & Presentation.

```mermaid
flowchart TD
    subgraph EdgeLayer["1. Edge Hardware & Simulation Layer"]
        ESP32["ESP32 Microcontroller\n(Dual Core, 240 MHz)"]
        DHT["DHT22 Sensor\n(Temp & Humidity)"] -->|GPIO 4| ESP32
        MQ["MQ-135 Gas Sensor\n(Air Quality / Gas)"] -->|Divider to GPIO 34| ESP32
        MIC["MAX9814 Microphone\n(Sound Peak-to-Peak)"] -->|GPIO 35| ESP32
        MockFeeder["Mock ESP32 Telemetry Feeder\n(tools/mock_esp32_feeder.py)"]
        SimEngine["In-Memory Simulator Engine\n(simulator.py)"]
    end

    subgraph TransportLayer["2. Ingestion & Communication Layer"]
        ESP32 -->|USB Serial @ 115200 baud\nNewline-Delimited JSON| SerialRecv["Serial Sensor Receiver\n(core/serial_sensor_receiver.py)"]
        ESP32 -->|HTTPS POST /api/v1/telemetry\nX-API-Key Auth| APIGateway["FastAPI Ingestion Gateway\n(backend/app.py)"]
        ESP32 -.->|MQTT TLS (Port 8883)\nsafeedge/devices/+/telemetry| HiveMQ["HiveMQ Cloud MQTT Broker"]
        HiveMQ -->|Subscriber Worker| MQTTBridge["Background MQTT Worker\n(backend/mqtt_worker.py)"]
        MockFeeder -->|Direct / Serial / HTTP| APIGateway
        MockFeeder -->|Direct Feed| SerialRecv
    end

    subgraph ServiceLayer["3. Persistence & Assessment Layer"]
        APIGateway --> SQLAlchemy["SQLAlchemy 2.0 ORM Engine"]
        MQTTBridge --> SQLAlchemy
        SQLAlchemy --> DB[("Database Storage\nSQLite / PostgreSQL")]
        APIGateway --> HazardEngine["Hazard Assessment Engine\n(core/hazard_assessment.py)"]
        HazardEngine --> HistoryTracker["Hazard History Tracker\n(core/hazard_history.py)"]
    end

    subgraph PresentationLayer["4. Dashboard & Reporting Layer"]
        SerialRecv --> Dashboard["Streamlit Industrial Cockpit\n(app.py)"]
        SimEngine --> Dashboard
        APIGateway -->|REST API\nGET /api/v1/telemetry/latest| CloudRecv["Cloud Sensor Receiver\n(core/cloud_sensor_receiver.py)"]
        CloudRecv --> Dashboard
        Dashboard --> Plotly["Real-Time Trend Visualizer\n(Plotly Interactive Charts)"]
        Dashboard --> CSVExport["Compliance CSV & Report Generator\n(safeedge_compliance_report.txt)"]
        Dashboard --> SafetyOfficers["Safety Officers & Site Commanders\n(HTTPS Web Browser)"]
    end
```

---

## 3. Hardware Component Specifications & Circuitry

The hardware layer is engineered for rapid prototyping and low-cost deployment:

| Component | Function / Role | Interface / Pin | Operating Voltage | Key Specifications & Constraints |
| :--- | :--- | :--- | :---: | :--- |
| **ESP32-WROOM-32** | Main System Controller | Dual-core Tensilica Xtensa 32-bit LX6 | 3.3V Logic | 240 MHz clock, 520 KB SRAM, 2.4 GHz Wi-Fi (802.11 b/g/n), Bluetooth v4.2 BR/EDR and BLE. |
| **DHT22 (AM2302)** | Ambient Temperature & Humidity | Single-bus Digital (GPIO 4) | 3.3V - 5.5V | Temp range: -40°C to +80°C (±0.5°C accuracy); Humidity range: 0% to 100% RH (±2-5% accuracy). 2-second sampling interval. |
| **MQ-135** | Hazardous Gas & Air Quality Sensor | Analog Out (GPIO 34 / ADC1_CH6) | 5.0V VCC (Heater) | SnO2 sensitive layer. Sensitive to NH3, NOx, Alcohol, Benzene, Smoke, CO2. Heater resistance: 31Ω ±3Ω. Requires 24-48h burn-in. |
| **MAX9814** | Ambient Acoustic Noise Monitor | Analog Out (GPIO 35 / ADC1_CH7) | 2.7V - 5.5V | Low-noise microphone amplifier with automatic gain control (AGC). 40dB/50dB/60dB programmable gain. Output centered at 1.25V bias. |
| **Resistor Voltage Divider** | Level Shifter for MQ-135 AO | 10kΩ and 20kΩ 1% Metal Film | Scaler | Protects ESP32 GPIO: scales 0-5.0V analog output down to 0-3.33V maximum safe input. |

### 3.1 ADC Pin Selection Rules
On the ESP32, ADC2 pins are shared with the Wi-Fi subsystem and fail or become corrupted when Wi-Fi is active. SafeEdge strictly mandates using **ADC1** pins:
- **GPIO 34 (ADC1_CH6)**: MQ-135 Gas Analog Input (Input-only, no pull-up/pull-down conflicts).
- **GPIO 35 (ADC1_CH7)**: MAX9814 Sound Analog Input (Input-only).

### 3.2 Removal of PMS5003 Particulate Sensor (Phase 4)
In Phase 4, the PMS5003 particulate-matter sensor ($25-$35 per unit, requiring dedicated UART wiring and 5V power) was removed from the system. This reduced the bill of materials (BOM) cost by over 60%, simplified wiring complexity, eliminated UART pin conflicts, and focused the safety system directly on volatile gases, thermal extremes, and acoustic hazards.

---

## 4. Software Stack & Framework Selection

The system is constructed with modern, production-grade Python technologies:

| Layer / Subsystem | Technology | Version | Purpose & Rationale |
| :--- | :--- | :---: | :--- |
| **Backend REST API** | FastAPI | 0.115+ | High-performance asynchronous API framework with automatic OpenAPI docs, strict Pydantic validation, and dependency injection. |
| **Data Validation** | Pydantic | 2.10+ | Strict type checking, boundary enforcement, and sanitized serializations for edge payloads. |
| **Database ORM** | SQLAlchemy | 2.0+ | Modern parameterized query engine supporting SQLite for local/embedded use and PostgreSQL for scalable cloud deployments. |
| **Web Dashboard** | Streamlit | 1.40+ | Real-time interactive UI with `@st.fragment(run_every="2s")` partial rendering for flicker-free telemetry updates. |
| **Interactive Plotting** | Plotly | 5.24+ | Hardware-accelerated SVG/WebGL charts supporting threshold reference lines, rolling windows, and peak annotations. |
| **MQTT Client** | paho-mqtt | 2.1+ | Standard MQTT protocol client supporting TLS (Port 8883) with background non-blocking reconnect loop. |
| **Testing Framework** | pytest | 9.2+ | Automated unit, integration, simulation, and security test runner with 100% passing suites. |

---

## 5. Communication Protocols & Telemetry Payloads

SafeEdge defines a unified, lightweight telemetry payload format across USB Serial, HTTPS REST, and MQTT.

### 5.1 Telemetry Schema (Phase 4 Revised)
Newline-delimited JSON payload transmitted at 0.5 Hz (every 2.0 seconds):
```json
{
  "device_id": "safeedge-esp32-01",
  "temperature_c": 28.4,
  "humidity_pct": 52.0,
  "gas_raw": 1350,
  "noise_raw": 1920,
  "device_timestamp": "2026-10-29T11:20:00Z"
}
```

### 5.2 Fault Tolerance & Null Representation
If an edge sensor becomes disconnected, unpowered, or suffers an I2C/OneWire communication timeout, the firmware explicitly outputs `null` for that specific field rather than fabricating zeros or false values:
```json
{
  "device_id": "safeedge-esp32-01",
  "temperature_c": null,
  "humidity_pct": null,
  "gas_raw": 1350,
  "noise_raw": 1920
}
```
The backend parser records the valid sensors while flagging `temp_valid=False` and `hum_valid=False` in the database, preventing false alarms and notifying technicians of hardware faults.

---

## 6. Sensor Calibration Requirements & Raw ADC Preservation

### 6.1 MQ-135 Gas Sensor Calibration Realities
The MQ-135 sensor utilizes an SnO2 semiconductor film whose surface resistance ($R_s$) decreases in the presence of deoxidizing gases. The sensor's response is governed by the power law:
$$R_s / R_0 = A \cdot (\text{ppm})^{-B}$$
Where:
- $R_0$ is the sensor resistance in clean ambient air at standard temperature (20°C) and humidity (65% RH).
- $A$ and $B$ are gas-specific constants empirically derived from logarithmic sensitivity curves.

**Critical Calibration Constraints:**
1. **Cross-Sensitivity**: The MQ-135 is non-selective; it simultaneously responds to NH3, NOx, Benzene, Alcohol, CO2, and smoke. Converting a raw ADC value directly to "ppm" without a calibrated gas chamber results in arbitrary, dangerously misleading numbers.
2. **Burn-in & Thermal Drift**: The internal heating element requires a 24- to 48-hour continuous preheat cycle to stabilize resistance.
3. **Ambient Sensitivity**: Ambient temperature and humidity alter $R_s$ by up to ±30%, requiring mathematical compensation.

**SafeEdge Design Decision:**  
In **Live Hardware Mode** and **Cloud Live Mode**, SafeEdge preserves and reports MQ-135 readings strictly as **Raw 12-bit ADC Counts (0 - 4095)**. The UI labels these readings with explicit `(uncalibrated)` badges. Only in **Simulation Mode** are values expressed in calibrated engineering units (ppm) for pedagogical demonstration.

### 6.2 MAX9814 Acoustic Microphone Module
The MAX9814 consists of an electret microphone capsule and an amplifier with Automatic Gain Control (AGC). While suitable for detecting relative acoustic surges (e.g. heavy equipment startup, explosions, structural collapse), converting raw peak-to-peak ADC voltage swings into standardized decibel sound pressure levels (dBA SPL) requires an acoustically anechoic chamber and a Type-1 sound level calibrator (IEC 61672-1). Therefore, live acoustic signals are reported strictly as raw peak-to-peak ADC amplitude counts.

---

## 7. Comprehensive Security Review & Audit Findings

SafeEdge was subjected to an extensive 5-dimension security audit (validated by `tests/test_security_audit.py`):

| Security Domain | Vulnerability Risk | SafeEdge Architectural Defense | Test Verification |
| :--- | :--- | :--- | :--- |
| **Authentication** | Unauthorized ingestion or data snooping | `verify_api_key` dependency enforces `X-API-Key` headers on all `/api/v1/telemetry*` and `/api/v1/devices` endpoints. Unauthenticated requests return `401 Unauthorized`. | `test_unauthenticated_requests_rejected`, `test_invalid_api_key_rejected` |
| **Credential Management** | Accidental leakage of keys or DB passwords | All credentials loaded from OS environment variables. `.env`, `*.env` strictly ignored by `.gitignore`. `.env.example` contains only placeholders. Zero secrets hardcoded. | Repository scan, `test_public_health_endpoints_accessible_without_key` |
| **SQL Injection** | Database tampering via crafted device IDs | All queries constructed exclusively with SQLAlchemy 2.0 ORM expressions (`filter(Model.field == param)`). Parameterized by the database driver; zero string interpolation. | `test_sql_injection_immunity_in_queries` with 5 hostile payloads |
| **Input Validation** | Buffer overflows, out-of-range ADC, XSS | Pydantic `TelemetryIngestPayload` enforces boundaries: Device ID 2-64 chars; Temp -40 to 85°C; Humidity 0-100%; ADC 0-65535. Rejecting NaN/Inf and negative numbers with 422. | `test_negative_adc_gas_reading_rejected`, `test_out_of_range_temperature_rejected`, `test_device_id_length_constraints` |
| **Cross-Origin Access** | Unauthorized web scraping / hijacking | FastApi `CORSMiddleware` restricted to explicit domain origins from `CORS_ORIGINS`. Disallowed origins receive 400 Bad Request on preflight. | `test_cors_headers_on_api` in `test_cloud_backend.py` |

---

## 8. Verification & Automated Testing Evidence

The SafeEdge codebase maintains a 100% automated test pass rate across 15 test suites and 175 test cases:

```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\Antigravity\safety from hazardeous gases
collected 175 items

tests/test_cloud_backend.py ..............                               [  8%]
tests/test_dashboard_integration.py ..........                          [ 13%]
tests/test_deployment_config.py ........                                [ 18%]
tests/test_end_to_end_simulation.py ........                             [ 22%]
tests/test_environmental_simulator.py .........................          [ 37%]
tests/test_esp32_firmware_compatibility.py ............                  [ 44%]
tests/test_gas_safety_integration.py ...                                 [ 45%]
tests/test_hazard_assessment.py .....................                    [ 57%]
tests/test_hazard_history.py ............                                 [ 64%]
tests/test_hazard_reporting.py .......................                   [ 77%]
tests/test_iot_hardware_simulator.py ...                                 [ 79%]
tests/test_mock_generator.py .......                                     [ 83%]
tests/test_mqtt_worker.py .........                                      [ 88%]
tests/test_security_audit.py ..............                              [ 96%]
tests/test_serial_sensor_receiver.py .......                             [100%]

======================== 175 passed, 1 warning in 5.87s =======================
```

### Test Suite Categories:
1. **Core Hazard Logic (`test_hazard_assessment.py`, `test_hazard_history.py`, `test_hazard_reporting.py`)**: Validates OSHA/NIOSH multi-parameter thresholds, warning escalations, event logging, and CSV/JSON report exports.
2. **Hardware Serial Communication (`test_serial_sensor_receiver.py`, `test_esp32_firmware_compatibility.py`)**: Validates 115200 baud streaming, newline-delimited JSON parsing, corrupted packet rejection, and reconnection loops.
3. **Cloud Ingestion & REST API (`test_cloud_backend.py`, `test_mqtt_worker.py`)**: Validates FastAPI endpoints, database ORM upserts, device status lifecycle, stale telemetry detection, and MQTT broker subscriptions.
4. **End-to-End Simulation (`test_end_to_end_simulation.py`, `test_mock_generator.py`)**: Verifies full pipelines without physical hardware, including stress-testing anomaly injection.
5. **Security & Boundary Enforcement (`test_security_audit.py`)**: Confirms authentication enforcement, SQL injection immunity, XSS containment, and parameter validation.

---

## 9. Safety, Regulatory & Compliance Disclaimers

> [!CAUTION]
> **PROTOTYPE CLASSIFICATION — NOT STATUTORY LIFE-SAFETY EQUIPMENT**
> 
> 1. **Educational & Engineering Prototype**: SafeEdge HazardGuard is designed as an advanced technical prototype demonstrating industrial IoT architecture, distributed telemetry, and algorithmic hazard assessment. It is **NOT** a certified life-safety device.
> 2. **Regulatory Standards**: It has not been tested or certified under OSHA 29 CFR 1910.1200, NIOSH guidelines, or European Norms (EN 50271 / EN 60079). It must **never** be used as the sole primary warning instrument in confined spaces, hazardous work zones, or atmospheres with potential explosive hazards.
> 3. **Intrinsically Safe Requirements**: Real-world operations in hazardous environments (Class I, Division 1/2 or ATEX Zones 0/1/2) legally require **Intrinsically Safe (IS)** certified equipment that guarantees no electrical spark or thermal surface can trigger gas ignition. The ESP32 and open breadboard circuits are not intrinsically safe.

---

## 10. Conclusion & Next Steps

Phase 7 successfully concludes all development, verification, security hardening, and documentation milestones for the SafeEdge HazardGuard platform. The software system is fully validated, robustly tested across 175 automated test cases, and ready for deployment or demonstration with both simulated feeds and real ESP32 hardware.

