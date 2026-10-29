/**
 * SafeEdge HazardGuard - ESP32 Physical Sensor Firmware.
 * Phase 4: Environmental & Hazardous Gas Telemetry Node (4 Parameters).
 * 
 * Hardware Sensors Integrated:
 * 1. DHT22: Temperature (°C) & Relative Humidity (%)
 * 2. MQ-135: Hazardous Air Quality Sensor (Raw ADC counts, uncalibrated)
 * 3. MAX9814: Microphone Amplifier Module (Peak-to-peak audio ADC counts, uncalibrated)
 * 
 * Output: One newline-delimited JSON line every 2 seconds via USB Serial @ 115200 baud.
 * Format:
 * {"device_id":"safeedge-esp32-01","temperature_c":31.5,"humidity_pct":64.0,"gas_raw":1250,"noise_raw":1850}
 * 
 * Safety & Regulatory Disclaimer:
 * This prototype firmware is for testing, demonstration, and preliminary prototyping.
 * Raw MQ-135 and microphone readings are uncalibrated and must NOT be used as
 * certified workplace safety measurements for OSHA, NIOSH, or statutory compliance.
 */

#include <Arduino.h>
#include <DHT.h>
#include "config.h"

// ============================================================================
// Sensor Driver Instances
// ============================================================================

// DHT22 (AM2302) on PIN_DHT
#define DHTTYPE DHT22
DHT dht(PIN_DHT, DHTTYPE);

// Timing Tracker
uint32_t last_telemetry_time = 0;

// ============================================================================
// Helper: Sample MQ-135 Gas Analog Sensor (ADC1)
// ============================================================================
uint16_t sample_mq135_raw() {
    uint32_t sum = 0;
    for (int i = 0; i < ADC_SAMPLES_COUNT; i++) {
        sum += analogRead(PIN_MQ135_ADC);
        delayMicroseconds(200);
    }
    return (uint16_t)(sum / ADC_SAMPLES_COUNT);
}

// ============================================================================
// Helper: Sample MAX9814 Microphone Peak-to-Peak Window (ADC1)
// ============================================================================
uint16_t sample_max9814_peak_to_peak() {
    uint32_t start_ms = millis();
    uint16_t min_val = ADC_MAX_COUNTS;
    uint16_t max_val = 0;

    // Sample audio waveform over a 50 ms window to capture acoustic amplitude
    while (millis() - start_ms < MIC_SAMPLE_WINDOW_MS) {
        uint16_t sample = analogRead(PIN_MIC_ADC);
        if (sample < min_val) min_val = sample;
        if (sample > max_val) max_val = sample;
    }

    if (max_val >= min_val) {
        return (max_val - min_val);
    }
    return 0;
}

// ============================================================================
// Setup
// ============================================================================
void setup() {
    // 1. Initialize USB Serial Link for telemetry output
    Serial.begin(SERIAL_BAUD_RATE);
    delay(500);

    // Initial diagnostic banner (prefixed with '//' so JSON receivers ignore safely)
    Serial.println("// SafeEdge HazardGuard ESP32 Sensor Node Initializing...");
    Serial.print("// Device ID: ");
    Serial.println(DEVICE_ID);
    Serial.print("// Telemetry Baud Rate: ");
    Serial.println(SERIAL_BAUD_RATE);

    // 2. Configure ESP32 ADC (12-bit, 0 - 3.3V full scale)
    analogReadResolution(ADC_RESOLUTION_BITS);
    analogSetAttenuation(ADC_11db);

    // 3. Initialize DHT22
    dht.begin();
    Serial.println("// DHT22 initialized on GPIO 4");

    // 4. Pin Mode Configurations
    pinMode(PIN_MQ135_ADC, INPUT);
    pinMode(PIN_MIC_ADC, INPUT);

    Serial.println("// MQ-135 ADC initialized on GPIO 34 (ADC1_CH6)");
    Serial.println("// MAX9814 Mic ADC initialized on GPIO 35 (ADC1_CH7)");
    Serial.println("// Initialization complete. Streaming telemetry...");

    last_telemetry_time = millis();
}

// ============================================================================
// Main Loop
// ============================================================================
void loop() {
    // Check if the 2-second telemetry interval has elapsed
    uint32_t now = millis();
    if (now - last_telemetry_time >= TELEMETRY_INTERVAL_MS) {
        last_telemetry_time = now;

        // --- Read DHT22 ---
        float temp_c = dht.readTemperature();
        float hum_pct = dht.readHumidity();
        bool dht_valid = (!isnan(temp_c) && !isnan(hum_pct) && 
                          temp_c >= -40.0f && temp_c <= 85.0f && 
                          hum_pct >= 0.0f && hum_pct <= 100.0f);

        // --- Read MQ-135 (Raw ADC count) ---
        uint16_t gas_raw = sample_mq135_raw();
        bool gas_valid = (gas_raw <= ADC_MAX_COUNTS);

        // --- Read MAX9814 (Peak-to-Peak Audio ADC count) ---
        uint16_t noise_raw = sample_max9814_peak_to_peak();
        bool noise_valid = (noise_raw <= ADC_MAX_COUNTS);

        // ====================================================================
        // Construct Single-Line JSON Telemetry String
        // Format:
        // {"device_id":"safeedge-esp32-01","temperature_c":31.5,"humidity_pct":64.0,"gas_raw":1250,"noise_raw":1850}
        //
        // Note: Failed / disconnected sensors are represented as null
        // ====================================================================

        char json_buffer[256];
        char temp_str[16];
        char hum_str[16];
        char gas_str[16];
        char noise_str[16];

        // Format Temperature
        if (dht_valid) {
            snprintf(temp_str, sizeof(temp_str), "%.1f", temp_c);
        } else {
            snprintf(temp_str, sizeof(temp_str), "null");
        }

        // Format Humidity
        if (dht_valid) {
            snprintf(hum_str, sizeof(hum_str), "%.1f", hum_pct);
        } else {
            snprintf(hum_str, sizeof(hum_str), "null");
        }

        // Format Gas (Raw MQ-135 ADC)
        if (gas_valid) {
            snprintf(gas_str, sizeof(gas_str), "%u", gas_raw);
        } else {
            snprintf(gas_str, sizeof(gas_str), "null");
        }

        // Format Noise (Raw Microphone Peak-to-Peak ADC)
        if (noise_valid) {
            snprintf(noise_str, sizeof(noise_str), "%u", noise_raw);
        } else {
            snprintf(noise_str, sizeof(noise_str), "null");
        }

        // Assemble full JSON payload
        snprintf(json_buffer, sizeof(json_buffer),
            "{\"device_id\":\"%s\",\"temperature_c\":%s,\"humidity_pct\":%s,\"gas_raw\":%s,\"noise_raw\":%s}",
            DEVICE_ID,
            temp_str,
            hum_str,
            gas_str,
            noise_str
        );

        // Transmit JSON line followed by newline
        Serial.println(json_buffer);
        Serial.flush();
    }
}
