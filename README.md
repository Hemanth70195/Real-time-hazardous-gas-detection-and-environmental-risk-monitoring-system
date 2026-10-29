# SafeEdge HazardGuard — Construction Site Hazardous Gas & Environmental Safety Monitoring System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![UI](https://img.shields.io/badge/Web%20App-Streamlit-red.svg)](https://streamlit.io/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-All%20Passing-brightgreen.svg)]()

**SafeEdge HazardGuard** is a dedicated real-time hazardous gas detection and environmental risk monitoring application for construction and industrial work sites.

It provides real-time multi-hazard monitoring across **Simulation Mode**, **Live Hardware Mode (USB Serial)**, and **Cloud Live Mode (IoT Streaming)** with automatic threshold assessments, actionable safety recommendations, historical trend tracking, and multi-format safety audit reports.

---

> [!NOTE]
> **Phase 4 System Update**: The PMS5003 particulate matter sensor has been removed from the platform to optimize budget, reduce hardware procurement costs, and simplify wiring. SafeEdge HazardGuard continuously monitors **4 environmental channels**: Temperature, Humidity, Noise, and Hazardous Gas.

---

## 1. Monitored Environmental Hazards

| Parameter | Unit / Signal | Baseline (Safe) | Warning (▲) | Danger (●) | Sensor & Transducer |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Temperature** | °C | `15.0 - 34.9` | `35.0 - 44.9` | `>= 45.0` | **DHT22** (Calibrated ambient dry-bulb) |
| **Relative Humidity** | % | `30.0 - 69.9` | `70.0 - 84.9` | `>= 85.0` | **DHT22** (Calibrated relative humidity) |
| **Ambient Noise** | dB / Raw ADC | `40.0 - 84.9` (sim) | `>= 85.0` (sim) | `>= 100.0` (sim) | **MAX9814** (Raw audio ADC in live hardware) |
| **Hazardous Gas** | ppm / Raw ADC | `0.0 - 24.9` (sim) | `25.0 - 49.9` (sim) | `>= 50.0` (sim) | **MQ-135** (Raw gas ADC in live hardware) |

> [!WARNING]
> **Uncalibrated Sensor Distinction**: In Live Hardware Mode and Cloud Live Mode, readings from the **MQ-135** gas sensor and **MAX9814** microphone module are treated strictly as **raw uncalibrated ADC counts (0 - 4095)**. They are NEVER classified as safe ppm or dB levels without a certified laboratory multi-point calibration.

---

## 2. Operating Data Source Modes

SafeEdge HazardGuard supports 3 distinct data source modes selectable from the sidebar:

1. **Simulation Mode**:
   - Synthesizes realistic sensor drift, micro-spikes, and physical bounds.
   - Provides preset emergency scenarios (*Acoustic Noise Stress*, *Gas Leak Danger*, *Heat Stress*, *Multi-Hazard*).
   - Fully interactive without any physical hardware.

2. **Live Hardware Mode (ESP32 Serial)**:
   - Receives real sensor telemetry from an ESP32 connected via USB serial at `115200` baud.
   - Non-blocking daemon receiver with automatic port discovery, checksum validation, and stale detection.

3. **Cloud Live Mode (IoT Streaming)**:
   - Ingests telemetry via FastAPI REST API (`/api/v1/telemetry`) or MQTT over TLS.
   - Persists historical readings into SQLite or PostgreSQL.
   - Seamless remote telemetry access from anywhere with internet connectivity.

---

## 3. Revised ESP32 Telemetry Format (Phase 4)

The ESP32 transmits newline-delimited JSON objects over serial or Wi-Fi every 2 seconds:
```json
{"device_id":"safeedge-esp32-01","temperature_c":31.5,"humidity_pct":64.0,"gas_raw":1250,"noise_raw":1850}
```
If a sensor is unplugged or faulty, the field value is set to `null` without fabricating data:
```json
{"device_id":"safeedge-esp32-01","temperature_c":null,"humidity_pct":null,"gas_raw":1250,"noise_raw":1850}
```

---

## 4. Installation & Setup

### Prerequisites
- Python 3.10+ (Python 3.14 recommended)
- Windows / Linux / macOS

```powershell
cd "D:\Antigravity\safety from hazardeous gases"

# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies (if not already installed)
pip install -r requirements.txt
```

---

## 5. Launching the System Locally

### Launch Monitoring Cockpit (Streamlit Web App)
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Open browser at: `http://localhost:8501`

### Launch Cloud Ingestion Backend (FastAPI Service)
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```
API docs available at: `http://localhost:8000/docs`
Health check diagnostics: `http://localhost:8000/health`

### Mock ESP32 Telemetry Feeder (Testing without Hardware)
```powershell
# Directly feed simulated live ESP32 serial packets into receiver:
.\.venv\Scripts\python.exe tools/mock_esp32_feeder.py --mode direct --interval 2.0 --scenario normal

# Test anomaly scenarios (e.g. gas-spike, high-temp, noise-spike, missing-sensors):
.\.venv\Scripts\python.exe tools/mock_esp32_feeder.py --mode direct --interval 2.0 --scenario gas-spike
```

### Local Multi-Container Production Stack (Docker Compose)
To run the full production stack locally with PostgreSQL:
```bash
docker-compose up --build
```
- Dashboard: `http://localhost:8501`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

---

## 6. Cloud Deployment Architecture (Phase 6)

SafeEdge HazardGuard uses a decoupled cloud architecture designed for zero hosting cost on free tiers:

```mermaid
flowchart TD
    ESP["ESP32 Physical Node\n(DHT22, MQ-135, MAX9814)"] -->|HTTPS JSON Telemetry\nPOST /api/v1/telemetry| Backend["FastAPI Backend Service\n(Render / Railway / Koyeb)"]
    ESP -.->|MQTT TLS (Port 8883)\nsafeedge/devices/+/telemetry| HiveMQ["Managed MQTT Broker\n(HiveMQ Cloud / EMQX)"]
    HiveMQ -->|Subscriber Worker| Backend
    Backend -->|Store Telemetry & Events| DB[("Managed PostgreSQL\n(Render / Neon / Supabase)")]
    Dashboard["Streamlit Public Dashboard\n(Streamlit Community Cloud)"] -->|GET /api/v1/telemetry/latest\nBearer API Key| Backend
    Dashboard -->|GET /api/v1/telemetry/history| Backend
    Admin["Safety Officers / Public"] -->|HTTPS Web Access| Dashboard
```

### Recommended Hosting Services

| Component | Recommended Service | Free Tier Allowance | Rationale & Trade-offs |
| :--- | :--- | :--- | :--- |
| **Public Dashboard** | **Streamlit Community Cloud** | 100% Free | Native Streamlit hosting linked directly to GitHub repo. Continuous auto-deploy on `git push`, auto-HTTPS, custom URL (`*.streamlit.app`), and built-in secrets management. |
| **API Backend** | **Render.com** (Web Service) | 750 free hrs/month | Native Python / Docker hosting with free automatic SSL/TLS. *Limitation:* Spins down after 15 min of inactivity; ~30s cold start delay on wake. |
| **Persistent Database**| **Render PostgreSQL** or **Neon** | Free Tier (0.5 - 1 GB) | Fully managed PostgreSQL with automatic TLS and schema persistence. Free tier SQLite volume alternative available. |
| **MQTT Broker** | **HiveMQ Cloud** | Free Tier (100 devices) | Fully managed MQTT over TLS (Port 8883), 10 GB/month data transfer, username/password access controls. |

---

## 7. Production Deployment Instructions

### Step 1: Deploy FastAPI Backend on Render.com
1. Create a free account at [render.com](https://render.com).
2. Click **New +** -> **Blueprint**.
3. Connect your GitHub repository: `https://github.com/Hemanth70195/Real-time-hazardous-gas-detection-and-environmental-risk-monitoring-system`.
4. Render automatically detects [`render.yaml`](render.yaml) and provisions:
   - A managed PostgreSQL database (`safeedge-postgres`).
   - A Python Web Service (`safeedge-backend`) with health checks at `/health`.
5. Once deployed, copy your backend public URL (e.g., `https://safeedge-backend.onrender.com`) and your generated `SAFEEDGE_API_KEY`.

### Step 2: Deploy Public Dashboard on Streamlit Community Cloud
1. Sign in to [share.streamlit.io](https://share.streamlit.io) using your GitHub account.
2. Click **New app** and select:
   - **Repository:** `Hemanth70195/Real-time-hazardous-gas-detection-and-environmental-risk-monitoring-system`
   - **Branch:** `main`
   - **Main file path:** `app.py`
3. Click **Advanced settings...** -> **Secrets** and enter:
   ```toml
   SAFEEDGE_BACKEND_URL = "https://safeedge-backend.onrender.com"
   SAFEEDGE_DEVICE_ID = "safeedge-esp32-01"
   SAFEEDGE_API_KEY = "your-render-generated-api-key"
   ```
4. Click **Deploy!** Your dashboard will be live at `https://<your-app-name>.streamlit.app`.

---

## 8. Environment Variables Reference

All runtime settings are read from environment variables (or Streamlit secrets). Copy [`.env.example`](.env.example) to `.env`:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `SAFEEDGE_BACKEND_URL` | `http://localhost:8000` | Public URL of the FastAPI backend service |
| `SAFEEDGE_DEVICE_ID` | `safeedge-esp32-01` | Default ESP32 hardware device identifier |
| `SAFEEDGE_API_KEY` | `safeedge-dev-api-key-2026` | API authentication key for ingestion and queries |
| `REQUIRE_API_KEY` | `true` | Enforce API key requirement on REST endpoints |
| `DATABASE_URL` | `sqlite:///safeedge_iot.db` | SQLAlchemy connection string (SQLite or PostgreSQL) |
| `STALE_TIMEOUT_SECONDS` | `5.0` | Max elapsed seconds before sensor telemetry is marked stale |
| `MQTT_BROKER_HOST` | `broker.hivemq.com` | MQTT broker hostname |
| `MQTT_BROKER_PORT` | `8883` | MQTT broker port (8883 for TLS) |
| `MQTT_USE_TLS` | `true` | Enable TLS encryption for MQTT connections |
| `CORS_ORIGINS` | `http://localhost:8501,...` | Comma-separated allowed CORS origins for browser access |

---

## 9. Connecting Physical ESP32 Hardware Later

When physical hardware is available:

1. **USB Serial Mode:** Connect ESP32 via USB. Open the public or local dashboard, select **Live Hardware Mode (USB Serial)**, choose the COM port, and click **Connect**.
2. **Cloud Wi-Fi Mode:** Configure Wi-Fi SSID, Wi-Fi Password, and the public backend URL (`https://your-backend.onrender.com/api/v1/telemetry`) in the ESP32 firmware sketch. The node transmits directly over HTTPS or secure MQTT from anywhere with internet connectivity.
3. **Sensor Pinout:**
   - **DHT22:** 3.3V, GND, DATA -> GPIO 4
   - **MQ-135:** 5V VIN, GND, AO -> 10k/20k Voltage Divider -> GPIO 34 (ADC1_CH6)
   - **MAX9814:** 3.3V, GND, OUT -> GPIO 35 (ADC1_CH7)

---

## 10. Running the Test Suite

Execute the complete automated test suite (175 unit, integration, simulation, and security tests):
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

---

## 11. Comprehensive Documentation & Demonstration

- **[System Demonstration Guide](docs/demonstration_guide.md)**: Complete step-by-step reproduction guide covering local startup, mock telemetry feeding, hazard spike injection, report exports, and physical hardware connection.
- **[Final Technical Project Report](docs/final_project_report.md)**: Exhaustive engineering report detailing problem statement, system architecture, circuit schematics, calibration physics, security audit evidence, and compliance disclaimers.

---

## 12. Safety & Compliance Disclaimer

> [!CAUTION]
> **PROTOTYPE SYSTEM - NOT CERTIFIED LIFE-SAFETY EQUIPMENT**
> SafeEdge HazardGuard is an educational, research, and engineering prototype. While designed to demonstrate industrial safety architecture, it does not constitute certified statutory safety equipment under OSHA 1926/1910, NIOSH, or EN standards. Real-world hazardous gas life safety requires intrinsically safe (ATEX/IECEx certified) instruments.
