-- Entities only. Sample data never goes in SQLite (docs/data-model.md).
-- All *_utc columns are UTC seconds as REAL (float64).

CREATE TABLE study (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    notes       TEXT NOT NULL DEFAULT '',
    created_utc REAL NOT NULL
);

CREATE TABLE participant (
    id          INTEGER PRIMARY KEY,
    study_id    INTEGER NOT NULL REFERENCES study(id) ON DELETE CASCADE,
    code        TEXT NOT NULL,              -- anonymous ID, e.g. "P07"
    created_utc REAL NOT NULL,
    UNIQUE (study_id, code)
);

CREATE TABLE scenario (
    id          INTEGER PRIMARY KEY,
    study_id    INTEGER NOT NULL REFERENCES study(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    position    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (study_id, name)
);

-- One per participant x scenario. A participant need not do every scenario.
CREATE TABLE recording (
    id             INTEGER PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
    scenario_id    INTEGER NOT NULL REFERENCES scenario(id) ON DELETE CASCADE,
    UNIQUE (participant_id, scenario_id)
);

-- Retakes. take_index is assigned by the app, never by the operator.
CREATE TABLE take (
    id               INTEGER PRIMARY KEY,
    uuid             TEXT NOT NULL UNIQUE,  -- names the directory under takes/
    recording_id     INTEGER NOT NULL REFERENCES recording(id) ON DELETE CASCADE,
    take_index       INTEGER NOT NULL,
    is_canonical     INTEGER NOT NULL DEFAULT 0 CHECK (is_canonical IN (0, 1)),
    status           TEXT NOT NULL DEFAULT 'recording'
                     CHECK (status IN ('recording', 'processing', 'done', 'failed', 'cancelled')),
    reference_stream TEXT,
    app_version      TEXT NOT NULL,
    started_utc      REAL NOT NULL,
    stopped_utc      REAL,
    UNIQUE (recording_id, take_index)
);
-- At most one canonical take per recording.
CREATE UNIQUE INDEX take_one_canonical ON take(recording_id) WHERE is_canonical = 1;

-- Devices are global, not owned by a study.
CREATE TABLE device_config (
    device_id    TEXT PRIMARY KEY,          -- adapter id: "bitalino", "tobii", "scaner"
    config_json  TEXT NOT NULL DEFAULT '{}',
    updated_utc  REAL NOT NULL
);

-- Summary of quality.json, written by the post-stop job.
CREATE TABLE quality_report (
    take_id            INTEGER PRIMARY KEY REFERENCES take(id) ON DELETE CASCADE,
    computed_utc       REAL NOT NULL,
    usable_start_utc   REAL,
    usable_end_utc     REAL,
    warning_count      INTEGER NOT NULL DEFAULT 0,
    summary_json       TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE app_event (
    id        INTEGER PRIMARY KEY,
    ts_utc    REAL NOT NULL,
    level     TEXT NOT NULL DEFAULT 'info',
    kind      TEXT NOT NULL,
    take_id   INTEGER REFERENCES take(id) ON DELETE SET NULL,
    message   TEXT NOT NULL DEFAULT '',
    data_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX app_event_ts ON app_event(ts_utc);
