-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Devices table (lightweight hardware registry)
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,         -- 'bitalino', 'tobii', 'scanner'
    address VARCHAR(255),              -- Bluetooth address, IP, etc.
    sample_rate INTEGER,               -- Hz (100, 1000, etc.)
    channels JSONB DEFAULT '[]',       -- configured channels, e.g. [{"code": 1, "label": "ecg"}]
    config JSONB DEFAULT '{}',         -- any other device-specific settings
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Recordings table (main organizational unit — flat + tags)
CREATE TABLE IF NOT EXISTS recordings (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,                  -- optional longer notes
    tags TEXT[] DEFAULT '{}',          -- searchable array: ['highway', 'P01', 'baseline']
    status VARCHAR(20) DEFAULT 'created',  -- 'created', 'running', 'stopped', 'exported'
    started_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    device_configs JSONB DEFAULT '[]', -- snapshot of device configs at recording start
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- GIN index for tag-based filtering
CREATE INDEX IF NOT EXISTS idx_recordings_tags ON recordings USING GIN (tags);

-- Sensor data hypertable
CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMPTZ NOT NULL,
    recording_id INTEGER NOT NULL REFERENCES recordings(id),
    device_id INTEGER NOT NULL REFERENCES devices(id),
    channel VARCHAR(50) NOT NULL,      -- e.g. 'ecg', 'gaze_x', 'gaze_y', 'pupil_left'
    value DOUBLE PRECISION NOT NULL,
    sequence BIGINT                    -- device sequence number (if available)
);

-- Convert sensor_data to a TimescaleDB hypertable
SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);

-- Index for querying by recording and device
CREATE INDEX IF NOT EXISTS idx_sensor_data_recording_device
    ON sensor_data (recording_id, device_id, time DESC);
