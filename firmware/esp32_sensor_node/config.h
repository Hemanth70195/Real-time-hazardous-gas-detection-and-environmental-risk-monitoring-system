#pragma once
/**
 * SafeEdge HazardGuard - ESP32 Sensor Node Hardware Configuration.
 * Phase 4: Environmental & Hazardous Gas Telemetry Node (4 Parameters).
 * 
 * Target Board: ESP32 Dev Module / ESP32-WROOM-32 / NodeMCU-32S
 * Communication: USB Serial @ 115200 baud
 * Logic Levels: 3.3V (All GPIO and ADC pins are 3.3V max)
 * Supported Sensors:
 *   1. DHT22 (Temperature & Humidity)
 *   2. MQ-135 (Raw Hazardous Air Quality / Gas ADC)
 *   3. MAX9814 (Raw Microphone Peak-to-Peak ADC)
 */

#ifndef SAFEEDGE_CONFIG_H
#define SAFEEDGE_CONFIG_H

// ============================================================================
// 1. Device Identification & Telemetry Settings
// ============================================================================
#define DEVICE_ID               "safeedge-esp32-01"
#define SERIAL_BAUD_RATE        115200
#define TELEMETRY_INTERVAL_MS   2000    // 2-second transmission cadence (0.5 Hz)

// ============================================================================
// 2. Pin Assignments (Provisional for ESP32-WROOM-32 30/38-pin DevKit)
// ============================================================================

// --- DHT22 Temperature & Humidity Sensor ---
// Requires 10k pull-up resistor from DATA to 3.3V (often built into module).
// Safe GPIO: GPIO 4 (Supports digital I/O, no boot strapping conflicts).
#define PIN_DHT                 4

// --- MQ-135 Hazardous Air Quality / Gas Sensor ---
// Heater requires 5.0V VCC (draws ~150 mA).
// IMPORTANT: Analog Output (AO) can reach 5.0V!
// A 2:1 or 10k/20k voltage divider MUST be used between AO and ESP32 pin:
//   MQ-135 AO ---> [ 10k Resistor ] ---> ESP32 GPIO 34
//                                   |
//                             [ 20k Resistor ]
//                                   |
//                                  GND
// Safe Pin: GPIO 34 (ADC1_CH6, input-only, safe when Wi-Fi/BT is active).
#define PIN_MQ135_ADC           34

// --- MAX9814 Microphone Amplifier Module ---
// Powered from 3.3V rail. Output centered at ~1.25V with audio swing 0-3.3V.
// Safe Pin: GPIO 35 (ADC1_CH7, input-only, safe when Wi-Fi/BT is active).
#define PIN_MIC_ADC             35

// ============================================================================
// 3. Sensor Acquisition & Sampling Constants
// ============================================================================

// ADC Configuration (ESP32 12-bit ADC: 0 to 4095 counts)
#define ADC_RESOLUTION_BITS     12
#define ADC_MAX_COUNTS          4095
#define ADC_SAMPLES_COUNT       16      // Oversampling average for analog pins

// MAX9814 Peak-to-Peak Window
#define MIC_SAMPLE_WINDOW_MS    50      // 50 ms window for peak audio amplitude

#endif // SAFEEDGE_CONFIG_H
