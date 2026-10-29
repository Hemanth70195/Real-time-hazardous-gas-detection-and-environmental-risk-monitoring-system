# SafeEdge HazardGuard — ESP32 Sensor Node Firmware (Phase 4)

Firmware implementation for collecting physical environmental telemetry using an ESP32 microcontroller and transmitting newline-delimited JSON streams over USB Serial or Wi-Fi to the SafeEdge HazardGuard monitoring cockpit.

> [!NOTE]
> **Phase 4 Architecture Update**: The Plantower PMS5003 particulate matter sensor has been removed from this release to optimize deployment cost, simplify electrical wiring, and conserve power. The sensor node actively supports **DHT22**, **MQ-135**, and **MAX9814**.

---

> [!WARNING]
> **STATUTORY SAFETY & REGULATORY DISCLAIMER**
> This prototype firmware and accompanying hardware design are intended for **engineering evaluation, rapid prototyping, and educational demonstration only**.
> - Analog readings from the **MQ-135** gas sensor and **MAX9814** microphone module are **uncalibrated raw ADC signals**.
> - They do **NOT** represent certified occupational exposure limits or calibrated statutory measurements (such as OSHA, NIOSH, ACGIH, or ISO standards).
> - Do **NOT** rely on this prototype as a sole life-safety device or primary hazardous gas alarm in industrial, confined-space, or hazardous construction environments.

---

## 1. Supported Board & Hardware Assumptions

- **Microcontroller**: ESP32-WROOM-32 / NodeMCU-32S / ESP32 DevKit V1 (30-pin or 38-pin).
- **Architecture**: Xtensa dual-core 32-bit LX6 @ 240 MHz.
- **Logic Level**: **3.3 V CMOS**. (Input pins cannot tolerate 5 V signals without level shifting).
- **ADC Subsystem**: 12-bit SAR ADC (`0 - 4095` counts), configured with 11 dB attenuation (~0 to 3.3 V full-scale range).
  - **Important**: All analog inputs use **ADC1** pins (GPIO 34 and GPIO 35), ensuring analog measurements remain fully operational when Wi-Fi is active (ADC2 is disabled by the ESP32 Wi-Fi subsystem).

---

## 2. Complete Electrical Wiring & Pin Configuration

| Sensor | Sensor Pin | ESP32 Pin | Voltage Rail | Circuit & Protection Notes |
| :--- | :--- | :--- | :--- | :--- |
| **DHT22 (AM2302)** | VCC | `3V3` | 3.3 V | Powered from ESP32 3.3 V rail. |
| | GND | `GND` | Ground | Common system ground. |
| | DATA | `GPIO 4` | 3.3 V Logic | Digital bidirectional 1-wire pin. Requires 10 kΩ pull-up resistor to 3.3 V (built into most 3-pin breakout modules). |
| **MQ-135** | VCC | `VIN` / `5V` | **5.0 V** | Heater requires 5.0 V VCC (draws ~150 mA). **Must NOT be powered from 3.3 V.** |
| | GND | `GND` | Ground | Common system ground. |
| | AO (Analog) | `GPIO 34` | 0 – 3.3 V | **CRITICAL: Voltage Divider Required.**<br/>On 5 V VCC, MQ-135 AO can output up to 5 V. Connect a voltage divider: $R_1 = 10\text{ k}\Omega$ from AO to GPIO 34, and $R_2 = 20\text{ k}\Omega$ from GPIO 34 to GND. |
| **MAX9814** | VDD | `3V3` | 3.3 V | Powered from ESP32 3.3 V rail. |
| | GND | `GND` | Ground | Common system ground. |
| | OUT (Audio) | `GPIO 35` | 0 – 3.3 V | Analog peak-to-peak audio output. Connected to ADC1_CH7. |
| | GAIN | Unconnected | Float | Leaves automatic gain control (AGC) at 60 dB. Connect to GND for 50 dB or VDD for 40 dB. |

### Pins Avoided (Bootstrapping & Flash Safety)
- `GPIO 6 - 11`: Hardwired to the ESP32 internal SPI flash memory. **Never use.**
- `GPIO 0, 2, 12, 15`: Bootstrapping strapping pins. Kept unconnected to avoid boot loops or flashing failures.

---

## 3. Required Arduino IDE Libraries

Install the following libraries via the Arduino IDE Library Manager (`Sketch` -> `Include Library` -> `Manage Libraries...`):

1. **DHT sensor library** (by Adafruit) — version `1.4.x`
2. **Adafruit Unified Sensor** (by Adafruit) — version `1.1.x` (dependency for DHT library)

---

## 4. Setup and Flashing Instructions

1. **Install ESP32 Board Package**:
   - Open Arduino IDE -> `File` -> `Preferences`.
   - Add the following URL to *Additional Boards Manager URLs*:
     ```text
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - Go to `Tools` -> `Board` -> `Boards Manager...`, search for `esp32` by *Espressif Systems*, and click **Install**.

2. **Select Board and Configuration**:
   - Board: `ESP32 Dev Module` (or `NodeMCU-32S`)
   - Upload Speed: `921600` (or `115200` if upload fails)
   - Flash Frequency: `80MHz`
   - Flash Mode: `QIO`
   - Flash Size: `4MB (32Mb)`
   - Partition Scheme: `Default 4MB with spiffs`
   - Port: Select the COM port corresponding to your ESP32 (e.g., `COM3`, `COM4` on Windows).

3. **Open and Flash**:
   - Open `firmware/esp32_sensor_node/esp32_sensor_node.ino`.
   - Click the **Verify** (checkmark) button to compile.
   - Click the **Upload** (arrow) button.
   - If the terminal displays `Connecting........_____.....`, press and hold the **BOOT** button on your ESP32 for 2 seconds until uploading commences.

---

## 5. Serial Telemetry Protocol

- **Baud Rate**: `115200` baud (8 data bits, no parity, 1 stop bit: `8N1`).
- **Cadence**: Exactly **one JSON object per line** every `2000 ms` (2 seconds), followed by a newline `\n`.

### Example Payload (All Sensors Healthy)
```json
{"device_id":"safeedge-esp32-01","temperature_c":31.5,"humidity_pct":64.0,"gas_raw":1250,"noise_raw":1850}
```

### Example Payload (Partial Sensor Disconnection / Failure)
If a physical sensor is unplugged, timed out, or returning non-physical values, the firmware sets the field value to `null`. It **never fabricates or guesses missing measurements**:
```json
{"device_id":"safeedge-esp32-01","temperature_c":null,"humidity_pct":null,"gas_raw":1250,"noise_raw":1850}
```

---

## 6. Sensor Warm-Up & Calibration Requirements

### MQ-135 Hazardous Air Quality Sensor
- **Pre-Heat Requirement**: The internal $\text{SnO}_2$ heating element requires **at least 24 to 48 hours** of continuous burn-in upon initial unboxing, and **3 to 5 minutes** of warm-up on subsequent power cycles before readings stabilize.
- **Why Readings Remain Raw**: The MQ-135 is cross-sensitive to Ammonia ($\text{NH}_3$), Nitrogen Oxides ($\text{NO}_x$), Alcohol, Benzene, Smoke, and $\text{CO}_2$. Translating raw ADC output into gas-specific ppm requires:
  1. Operating in clean reference air to calculate base sensor resistance ($R_0$).
  2. Ambient temperature and relative humidity compensation curves.
  3. Controlled calibration chamber exposures against certified reference gases.
  Without laboratory calibration, SafeEdge treats all MQ-135 telemetry strictly as **raw uncalibrated ADC counts** and refuses to classify raw signals as safe ppm levels.

### MAX9814 Microphone Sound Sensor
- **Acoustic Sampling**: The firmware samples the audio envelope across a **50 ms window** using 16-point oversampling on ADC1_CH7 to calculate peak-to-peak amplitude.
- **Why Readings Remain Raw**: Converting raw analog microphone amplitude into certified acoustic decibels ($\text{dB}$ or $\text{dBA}$) requires frequency-weighting filters (A-weighting curve), standardized fast/slow exponential time averaging, and calibration against a certified $94\text{ dB} / 114\text{ dB}$ sound calibrator. Readings are treated as **uncalibrated acoustic intensity units**.

---

## 7. Troubleshooting

| Symptom | Probable Cause | Corrective Action |
| :--- | :--- | :--- |
| `DHT22 returning null / NaN` | Missing pull-up resistor or loose wire | Ensure DATA is connected to GPIO 4. Add a 10 kΩ resistor between DATA and 3.3 V if using bare sensor. |
| `MQ-135 reading 0 or 4095 constantly` | Incorrect voltage or burned sensor | Verify MQ-135 is powered from **5 V**, not 3.3 V. Verify the 10k/20k voltage divider on GPIO 34. Allow heater to warm up. |
| `MAX9814 reading 0 constantly` | Ground loop or bad connection | Ensure MAX9814 VDD is 3.3 V and OUT is connected to GPIO 35. Tap the mic to test peak-to-peak response. |
| `Serial Monitor outputs gibberish` | Baud rate mismatch | Set Serial Monitor to **115200 baud**. |
| `Python receiver reports STALE` | ESP32 disconnected or not transmitting | Re-plug USB cable, verify COM port in SafeEdge dashboard, and click **Connect ESP32**. |
