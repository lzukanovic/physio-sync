-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,         -- 'bitalino', 'tobii', 'scanner'
    address VARCHAR(255),              -- Bluetooth address, IP, etc.
    config JSONB DEFAULT '{}',         -- Device-specific configuration
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Recordings table
CREATE TABLE IF NOT EXISTS recordings (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'created',  -- 'created', 'running', 'stopped', 'exported'
    started_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Junction table: which devices participate in a recording
CREATE TABLE IF NOT EXISTS recording_devices (
    recording_id INTEGER REFERENCES recordings(id) ON DELETE CASCADE,
    device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
    PRIMARY KEY (recording_id, device_id)
);

-- Sensor data hypertable
CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMPTZ NOT NULL,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    recording_id INTEGER NOT NULL REFERENCES recordings(id),
    channel VARCHAR(50) NOT NULL,      -- e.g. 'ecg', 'gaze_x', 'gaze_y', 'pupil_left'
    value DOUBLE PRECISION NOT NULL,
    sequence BIGINT                    -- device sequence number (if available)
);

-- Convert sensor_data to a TimescaleDB hypertable
SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);

-- Index for querying by recording and device
CREATE INDEX IF NOT EXISTS idx_sensor_data_recording_device
    ON sensor_data (recording_id, device_id, time DESC);
