# Data model

## Entities (SQLite)

```
Study
├── Participant        (anonymous user ID, unique within study)
└── Scenario
        └── Recording  (one per participant × scenario)
                └── Take   (retakes; exactly one marked canonical)
```

Rules:

- A participant does not necessarily perform every scenario.
- A Recording is the pairing of one participant and one scenario within a study.
- Takes are implicit: the operator clicks "record again" and a new take appears.
  They are never manually named or indexed. The canonical one defaults to the
  most recent and can be changed.
- **Devices are global**, not owned by a study. They carry connection state and
  configuration, not data.

Tables: `study`, `participant`, `scenario`, `recording`, `take`, `device_config`,
`quality_report`, `app_event`. Sample data is never in SQLite.

Participant import accepts comma- or newline-separated IDs pasted or uploaded
as CSV.

## On disk

```
$PHYSIOSYNC_DATA/
  physiosync.db
  takes/
    <take-uuid>/
      manifest.json
      raw/                      # capture output, append-only, named by stream id
        bitalino.main.jsonl.gz
        tobii.gaze.jsonl.gz
        tobii.imu.jsonl.gz
        scaner.telemetry.jsonl.gz
      bitalino.main.parquet     # post-stop conversion
      tobii.gaze.parquet
      tobii.imu.parquet
      scaner.telemetry.parquet
      synced.parquet            # all streams on the reference axis
      tobii_device/             # files pulled from the glasses
        recording.g3
        gazedata.gz
        imudata.gz
      quality.json
```

JSONL during capture because it is append-only and survives a crash mid-write.
One JSON object per sample per line, keys in the stream's column order, `null`
for a value the device did not provide. Flushed and fsynced every second, so a
crash loses at most that; a file cut off by a crash decodes up to its last flush.
Opened exclusive-create, so a closed capture file can never be reopened (ADR 0010).
Parquet after, because it is what the charts and exports read. The `raw/` folder
is kept, not deleted — it is the evidence trail for the evaluation chapter.

## Manifest

**The manifest is the authoritative record of a take; SQLite is a rebuildable
index over `takes/` (ADR 0011).** A take directory stays valid when copied between
machines, and importing an existing take is a directory scan.

Written by the session manager at create, after the adapters start, and at stop;
the post-stop job later fills what only it can derive (Tobii epoch, `coverage_utc`
for Tobii, `usable_window`). `stopped_utc` still null means the take is recording
or crashed.

```json
{
  "schema_version": 1,
  "uuid": "...",
  "study_id": 3, "participant_id": "P07", "scenario_id": 2, "take_index": 2,
  "app_version": "0.3.0",
  "created_utc": 1789912931.482,
  "started_utc": 1789912931.483,
  "stopped_utc": 1789913236.120,
  "wall_monotonic_delta": [1789650152.4410, 1789650152.4412],
  "reference_stream": "scaner.telemetry",
  "streams": {
    "tobii.gaze": {
      "channels": ["gaze2d_x", "gaze2d_y", "..."],
      "nominal_hz": 100,
      "source": "tobii",
      "epoch_utc": 1774477258.390783,
      "epoch_method": "derived:min(local_ts-device_ts)",
      "epoch_uncertainty_s": 0.0008,
      "coverage_local": [0.0, 303.72],
      "coverage_utc": [1774477258.39, 1774477562.11],
      "n_samples": 30412
    },
    "tobii.imu": { "...": "same device clock; carries the same epoch as tobii.gaze" },
    "bitalino.main": {
      "channels": ["A1", "A2", "..."],
      "nominal_hz": 100,
      "source": "bitalino",
      "epoch_utc": 1774477264.901,
      "epoch_method": "host:t_start",
      "epoch_uncertainty_s": null,
      "coverage_local": [1774477264.901, "..."],
      "coverage_utc": [1774477264.901, "..."],
      "n_samples": "..."
    }
  },
  "usable_window": [1774477264.901, 1774477560.02],
  "warnings": ["tobii.ntp_not_synchronized"]
}
```

Streams are keyed by stream id, not by channel (ADR 0007). `source` is the adapter
id that produced the stream (`replay:tobii` for replayed data). `epoch_utc`,
`coverage_utc` and `n_samples` are `null` until known: a manifest read mid-capture is valid, and
the Tobii epoch stays `null` until the post-stop job derives it. All timestamps
are UTC float64 seconds, `created_utc` included. `participant_id` is the
participant code, so the manifest is readable without the database.

`coverage_local` is the first and last value of the stream's own time column
(`t` for BITalino, `device_ts` for Tobii), set at stop for every stream.
`coverage_utc` is the same interval in UTC: equal to `coverage_local` when that
column is already UTC (BITalino `t`), otherwise `epoch_utc` plus it, so for Tobii
it stays `null` until the post-stop job derives the epoch (ADR 0012). BITalino's
`coverage_utc` end may fall a few tens of ms after `stopped_utc`: `t` is the
nominal-rate reconstruction, not the arrival time.

`study_id`, `participant_id`, `scenario_id` and `take_index` are `null` for a
take recorded outside a study (e.g. a replay from `devcheck`).

`wall_monotonic_delta` is `time.time() − time.monotonic()` at start and at stop.
The absolute value is meaningless (the monotonic origin is arbitrary); only
`stop − start` is: how far the host wall clock was stepped or slewed during the
take. Flagged in the quality report above a threshold (Phase 3).

`usable_window` is the intersection of all streams' `coverage_utc`.

## Ragged starts

Streams do not begin together. In the sample data, Tobii started 6.73 s before
SCANeR and BITalino 1.39 s before.

The synced table covers the **full reference axis**. Streams that were not yet
recording get **nulls**, not trimmed rows. Parquet stores nulls natively and they
arrive as NaN in pandas. A null means "this sensor was not recording", which is
semantically different from a gap or a dropped sample and must stay
distinguishable.

The UI shows `usable_window` on the timeline. Export offers full axis or trimmed
to `usable_window`; trimmed is the default for synced exports.

## Quality report

Computed by the post-stop job, stored as `quality.json` and summarised into
SQLite. Shown in the UI and used as the source of evaluation numbers.

Per stream: sample count, expected count, coverage interval, measured vs nominal
rate, gap list (start, duration, samples missing), duplicate/out-of-order count.

BITalino: `nSeq` continuity violations with magnitudes, ambiguous wrap boundaries
if wrapping is observed, actual rate from `(N−1)/(t_end − t_start)` vs nominal,
and max divergence between `t` and `t_endanchored`.

Tobii: derived epoch and its uncertainty, `system.time` vs host clock at start and
at stop (offset and drift), `ntp-is-synchronized` at connect, valid-gaze fraction,
and — once device-side files are downloaded — the count of samples present in the
device recording but missing from the live capture.

Take-level: reference stream, usable window, streams with warnings, app version.
