# Fixtures

Committed test inputs. They exist so the replay adapter and `pytest` run with no
hardware attached, and so the golden-file test has something deterministic to
compare against.

---

## `live-capture/`

**What it is.** Output of the two prototype apps (`bitalino-mvp`, `tobii-mvp`) —
the format a **live stream** produces, which is what the replay adapter must
imitate. 180 seconds per stream.

| File             | Rows  | Span     | Rate     | Notes                                                         |
| ---------------- | ----- | -------- | -------- | ------------------------------------------------------------- |
| `bitalino.csv`   | 18000 | 179.94 s | 100.0 Hz | `Sequence` 0–17999 unbroken; `Timestamp` is host arrival time |
| `tobii_gaze.csv` | 17878 | 179.09 s | 99.8 Hz  | `DeviceTS` relative to stream open, `LocalTS` arrival         |
| `tobii_imu.csv`  | 23481 | 180.45 s | 130.1 Hz | magnetometer at 9.8 Hz; other rows leave those columns empty  |

### Provenance

These are **derived**, not raw captures. Each was extended to 180 s from a
shorter real recording — 16 s for BITalino (`recording_20260222_201500.csv`),
7 s for the Tobii pair (`*_20260325_231244.csv`) — by repeating the recorded
patterns and continuing the timestamps. The originals were too short to exercise
sustained writing or the decimator's drop path.

Timing characteristics were preserved and verified after extension:

- BITalino holds 100 Hz with unbroken sequence numbering, delivered in Bluetooth
  bursts of ~3.3 samples, 1.27 ms apart within a burst and 30.1 ms between.
- Tobii gaze and IMU are strictly monotonic in `DeviceTS`, with the derived
  epoch (`min(LocalTS − DeviceTS)`) stable to ~117 ms across the stream.

One defect was corrected during preparation: the extension gave the IMU
magnetometer its own clock running ~1.4 s behind the accelerometer and
gyroscope, and interleaved those rows by position rather than by time, producing
333 out-of-order samples. The magnetometer's `DeviceTS` was rebuilt from
`LocalTS` using the epoch derived from the accel/gyro rows, and the file
re-sorted. Epoch spread went from 1486 ms to 117 ms.

**Sample values repeat on a cycle.** Fine for timing and plumbing; nothing about
signal content should be concluded from this fixture.

### The three streams are not mutually synchronised

The two Tobii files are one session. The BITalino file was recorded on a
different day. The replay adapter rebases every stream onto session t=0 so all
three play together, but the alignment between Tobii and BITalino here is
meaningless.

**Use it for:** the replay adapter, capture pipeline, writers, decimator, live
feed, and any test of per-stream timestamp handling — arrival bursts, `Sequence`
continuity, Tobii epoch derivation.

**Do not use it for:** anything about cross-device alignment or reference-axis
selection. Those need `study-session/`.

---

## `study-session/` — not yet present

A trimmed excerpt of a real three-device study session supplied by the project
supervisor, in `../EDA-Bitalino-Tobii-Example-2/`. Added when Phase 3 needs it.

It is the only data where all three devices ran concurrently, started manually on
three separate machines, so the offsets between the streams are genuine capture
offsets rather than artefacts. That makes it the fixture for alignment work.

**Important limitation when it is added.** That data is _post-export_, not live
capture: BITalino comes from OpenSignals (`.h5`/`.txt`), Tobii from the
device-side SD card recording where t=0 is the first scene camera frame, SCANeR
from the simulator's own log. The exports have already removed the phenomena
this platform exists to handle — Bluetooth burst arrival, sequence gaps, the
relative-epoch problem. It must not be used to validate timestamp
reconstruction.

Note that `EDA-Bitalino-Tobii-Example-2/bitalino/prototype_bluetooth_recording_20260222_201500.csv`
is **not** study data: it is a copy of the same prototype recording used here,
included there as a live-format reference. The study's BITalino data is the
`.h5`/`.txt` pair.

**Before committing it:** confirm with the supervisor that the sample is cleared
for public redistribution. It is pseudonymous data from real participants
(`froddo_hmi_study_095`), and gaze plus physiological signals is not a trivial
category under GDPR. If clearance is unclear, keep it out of the repository and
document here how to generate it locally instead.

---

## Synthetic data

Not needed yet. When Phase 6 requires long unattended runs, or when the quality
report needs validating against known faults (dropped samples, Bluetooth stalls,
clock steps), a generator can produce streams in these same formats alongside a
`truth.json` listing exactly what was injected. Real captures contain no such
faults, so they cannot test detection of them.

Generated data is never committed.
