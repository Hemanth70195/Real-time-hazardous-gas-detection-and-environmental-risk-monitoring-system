-- SafeEdge HazardGuard - Cloud IoT PostgreSQL Production DDL Schema (Phase 3)
-- Execute this script in your PostgreSQL database (e.g. Supabase, AWS RDS, Neon, Google Cloud SQL)

-- 1. Devices Registry Table
CREATE TABLE IF NOT EXISTS devices (
    device_id VARCHAR(64) PRIMARY KEY,
    display_name VARCHAR(128) NOT NULL,
    firmware_version VARCHAR(32) DEFAULT '2.0.0',
    status VARCHAR(32) DEFAULT 'ONLINE',
    last_seen TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen DESC);

-- 2. Environmental Telemetry Table
CREATE TABLE IF NOT EXISTS telemetry_readings (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    server_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    device_timestamp VARCHAR(32),
    
    -- Calibrated environmental physical readings
    temperature_c DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    
    -- Raw uncalibrated ADC counts (CRITICAL: NOT ppm or dB)
    gas_raw DOUBLE PRECISION,
    noise_raw DOUBLE PRECISION,
    
    -- Validity indicators (distinguishes sensor fault from 0.0)
    temp_valid BOOLEAN DEFAULT TRUE,
    hum_valid BOOLEAN DEFAULT TRUE,
    gas_valid BOOLEAN DEFAULT TRUE,
    noise_valid BOOLEAN DEFAULT TRUE,
    
    -- Provenance and Calibration Metadata
    is_gas_calibrated BOOLEAN DEFAULT FALSE,
    is_noise_calibrated BOOLEAN DEFAULT FALSE,
    data_source VARCHAR(32) DEFAULT 'cloud_esp32',
    raw_payload TEXT
);

-- Fast lookup indexes for device time-series queries
CREATE INDEX IF NOT EXISTS idx_telemetry_device_id ON telemetry_readings(device_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_server_ts ON telemetry_readings(server_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_device_ts ON telemetry_readings(device_id, server_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_data_source ON telemetry_readings(data_source);

