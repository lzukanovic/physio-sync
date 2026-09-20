# 0007 — Manifest streams are keyed by stream, epochs may be null

**Context.** The first manifest example mixed stream-level keys (`tobii.gaze`)
with channel-level keys (`bitalino.A1`). BITalino delivers all configured channels
in one frame on one clock, Tobii gaze and IMU are separate streams on one device
clock, and SCANeR is expected to be a single multi-channel stream.

**Decision.** `streams` is keyed by stream id (`<adapter>.<stream>`, e.g.
`bitalino.main`, `tobii.gaze`, `tobii.imu`, `scaner.telemetry`), each listing its
`channels`. Streams of one device may carry the same epoch; each still records it.
`epoch_utc`, `coverage` and `n_samples` are nullable, because the Tobii epoch is
derived post-stop and coverage is unknown while capture is open. All timestamps,
including `created_utc`, are UTC float64 seconds.

**Consequences.** `reference_stream` and the chart API address streams, with
channels selected within them. A manifest read mid-capture is valid and
distinguishes "not yet known" (null) from a measured value. The participant is
stored by code (`P07`) so a manifest is readable without the database.
