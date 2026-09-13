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
      raw/                      # capture output, append-only
        bitalino.jsonl.gz
        tobii_gaze.jsonl.gz
        tobii_imu.jsonl.gz
        scaner.jsonl.gz
      bitalino.parquet          # post-stop conversion
      tobii_gaze.parquet
      tobii_imu.parquet
      scaner.parquet
      synced.parquet            # all streams on the reference axis
      tobii_device/             # files pulled from the glasses
        recording.g3
        gazedata.gz
        imudata.gz
      quality.json
```

JSONL during capture because it is append-only and survives a crash mid-write.
Parquet after, because it is what the charts and exports read. The `raw/` folder
is kept, not deleted — it is the evidence trail for the evaluation chapter.

## Manifest

Written incrementally during capture, finalised by the post-stop job.

```json
{
  "uuid": "...",
  "study_id": 3, "participant_id": "P07", "scenario_id": 2, "take_index": 2,
  "app_version": "0.3.0",
  "created_utc": "2026-09-20T14:02:11.482Z",
  "reference_stream": "scaner.telemetry",
  "streams": {
    "tobii.gaze": {
      "epoch_utc": 1774477258.390783,
      "epoch_method": "derived:min(local_ts-device_ts)",
      "epoch_uncertainty_s": 0.0008,
      "coverage": [1774477258.39, 1774477562.11],
      "n_samples": 30412,
      "nominal_hz": 100
    },
    "bitalino.A1": {
      "epoch_utc": 1774477264.901,
      "epoch_method": "host:t_start",
      "coverage": [...], "n_samples": ..., "nominal_hz": 100
    }
  },
  "usable_window": [1774477264.901, 1774477560.02],
  "warnings": ["tobii.ntp_not_synchronized"]
}
```

`usable_window` is the intersection of all stream coverage intervals.

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
