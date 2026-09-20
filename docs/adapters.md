# Adapters

Every source of data implements the same interface. This is the seam that keeps
devices independent of each other and makes the reference stream a configuration
choice rather than a structural one.

## Contract

```python
class SourceAdapter(Protocol):
    id: str                    # "bitalino", "tobii", "scaner", "replay:tobii"
    streams: list[StreamSpec]  # what this adapter produces

    async def probe(self) -> DeviceStatus: ...
    async def configure(self, cfg: dict) -> None: ...
    async def start(self, sink: SampleSink) -> StreamEpochs: ...
    async def stop(self) -> StopInfo: ...
```

Rules that hold for every adapter, without exception:

- **Never resample, interpolate, filter, or reorder.** Emit what the device gave
  you, with the timestamp rules below. All alignment happens in the post-stop job.
- **Never talk to another device.** No adapter may depend on another being
  present. This is the modularity requirement; event anchoring across devices was
  evaluated and rejected for exactly this reason (see
  `docs/decisions/0004-no-cross-device-anchoring.md`).
- **Emit sample batches, not single samples.** One batch per device callback or
  per WebSocket message.
- **Report health, do not decide.** Anomalies go into the quality report; the
  adapter does not silently correct them.
- **Stopping must be safe at any time**, including mid-batch and while
  disconnected.

`StreamEpochs` maps each stream to its absolute epoch in UTC seconds, or `None`
if the epoch must be derived post-hoc (Tobii). `StopInfo` carries stop wall-clock
time, sample counts, and anomalies.

---

## BITalino

Bluetooth, PLUX Python SDK.

**Vendored binaries.** The PLUX API ships compiled extension modules per OS,
architecture, and Python minor version, with no PyPI distribution. Vendor only
the folders for Python 3.10 on the platforms actually used — `Win64_310` for the
lab machine and one Mac folder (`M1_310` or `MacOS/Intel310`) for development —
into `src/physiosync/vendor/PLUX-API-Python3/`. Do not vendor the full upstream
set; folders that cannot run are noise in the repo and in the wheel. Add a
`README.md` alongside them recording the upstream source and commit.

Windows coverage upstream is 37, 38, 39, 310, 313 only. This is what forces the
project to Python 3.10 (see `CLAUDE.md`).

**Binary loader.** Port the logic from `bitalino-mvp`, but with two changes.
Resolve the vendor directory from the package root rather than by traversing
parent directories with `os.pardir`, so it survives a file move — use
`importlib.resources.files("physiosync") / "vendor" / "PLUX-API-Python3"`. And
fail loudly: if the resolved platform folder does not exist, raise with the
expected path and the detected platform in the message. A bare
`ModuleNotFoundError: plux` is useless at 9am on a measurement day.

**The device has no clock and does not timestamp samples.** Each frame carries a
sequence number `nSeq` and channel values. Arrival time is unreliable: samples
arrive in Bluetooth bursts, several sharing nearly the same arrival instant, then
a gap. Arrival time reflects packet delivery, not sampling.

Write three columns:

| Column       | How                                 | Role                                                                               |
| ------------ | ----------------------------------- | ---------------------------------------------------------------------------------- |
| `t`          | `t_start + nSeq / f_nominal`        | **Canonical.** Computed at capture time so live display and streaming writes work. |
| `arrival_ts` | `time.time()` on the frame callback | Diagnostic only. Never used for alignment.                                         |
| `nseq`       | as received, unwrapped              | Loss detection, and lets end-anchored `t` be derived later.                        |

`t_start` is host wall-clock captured immediately before the start command
returns. It is a host timestamp; there is no device-side anchor and none is
sought.

**End-anchored timestamps are not written at capture time.** The variant
`t_start + nSeq · (t_end − t_start)/(N−1)` is derived in the post-stop job into
the Parquet file as `t_endanchored`, so the accuracy comparison runs off archived
recordings rather than needing fresh captures.

**Sequence continuity.** Assert `nSeq` increases by exactly 1 per frame. Log
every violation with its magnitude into the quality report. Whether the SDK hands
back a raw 4-bit field (wrapping every 16 samples) or an already-unwrapped
counter must be established by measurement on the first real capture, not
assumed — it changes whether losses that are multiples of 16 are detectable, and
the thesis makes a claim about this. If wrapping is observed, unwrap here in the
adapter and record the ambiguous-boundary count.

Default sampling rate 100 Hz. The configured channels are chosen by the operator.

---

## Tobii Pro Glasses 3

Network (Ethernet, lab WiFi, or the glasses' own access point). HTTP + WebSocket
API on the recording unit, accessed through **g3pylib**, pinned by commit to the
lab's fork (see `CLAUDE.md`). Not the `tobii-research` package, which is for
screen-based trackers.

The timestamp rules below apply to whatever g3pylib surfaces from the signal
body; if it exposes the raw `[timestamp, data]` array, the first element is the
relative device timestamp described here. Verify this against `tobii-mvp` rather
than assuming the library normalises it.

Support discovery via Zeroconf
(`_tobii-g3api._tcp`), mDNS (`<serial>.local`), the AP-mode fixed address
`192.168.75.51`, and manual entry. Build the REST base path from the Zeroconf
`path` property rather than hardcoding `/rest/`.

**Stream timestamps are relative, not absolute.** All streams share one physical
clock and never drift against each other, but each API object computes its own
zero at creation time. A gaze sample reads e.g. `681.751` — seconds since the
stream was opened. Verified against `tobii-mvp` output: `DeviceTS` runs 0.80 →
4.40 while `LocalTS` is a Unix epoch.

Write both columns, as the MVP already does:

| Column      | How                                                               |
| ----------- | ----------------------------------------------------------------- |
| `device_ts` | the stream's own timestamp. **Canonical after epoch correction.** |
| `local_ts`  | `time.time()` on message arrival. Used only to derive the epoch.  |

**Epoch derivation (post-stop job).** Take `min(local_ts − device_ts)` over the
stream, or the median after discarding the first second. Do not use the first
sample: measured data shows the opening burst gives 258.4985 while the settled
value is 258.3914, a 100 ms error, and the full-file spread is ~1.5 s. Write the
result to the manifest as the stream epoch; absolute time is `epoch + device_ts`.

**At connect:** read `system.ntp-is-synchronized`. If false, surface a prominent
warning in the UI and tag the recording. Do not block, but do not let it pass
silently. Also read `system.time` at start and again at stop and store both; this
gives an independent measurement of host-vs-glasses clock offset and its drift
across the session, which is evaluation material.

**Device-side recording.** Also call `recorder!start` / `recorder!stop`. After
stopping, download the small files over HTTP (`recording.g3`, `gazedata.gz`,
`imudata.gz`) via `recordings/<uuid>.http-path`. These are full-rate, written
device-side, immune to WiFi loss, and carry `created` as an absolute UTC
timestamp — a free cross-check on the live capture and on the derived epoch.
**The scene video mp4 is deliberately not downloaded yet** (~1.2 GB for 30 min);
it is deferred to the playback phase. Everything else about this path is built now.

Live scene video is WebRTC for operator monitoring only, never stored. Call
`webrtc/<uuid>!keep-alive` at least every 5 s or the session terminates at 20 s.

Gaze runs 50 or 100 Hz (configurable on 100 Hz units); IMU accelerometer and
gyroscope ~100 Hz nominal (measured ~121 Hz); magnetometer ~10 Hz. IMU samples
may contain readings from only some sensors — write nulls, do not drop the row.

---

## SCANeR

Specifics are not yet available from the lab, but a real export exists at
`../EDA-Bitalino-Tobii-Example-2/datalogger/` and should be inspected before this
adapter is designed. Its observed shape:

```
user_95_scenario_99923_repeat_1/
├── user_95_scenario_99923_repeat_1.csv        # the telemetry stream
├── user_95_scenario_99923_repeat_1_info.csv   # run metadata
├── objectsLookupTable.json                    # id → object name mapping
└── record/
    ├── criterionResults.csv
    └── simulation.result.db                   # SQLite
```

Note that the folder name already encodes user, scenario, and repeat — the same
hierarchy as this platform's Participant × Scenario × Take. Whether the platform
should parse that naming, or write it, is worth deciding rather than defaulting.

The adapter supports three acquisition modes behind the same interface; build
them in this order.

1. **Post-hoc import.** Nothing captured live. After stopping, read the run's
   export folder and import the telemetry CSV as a stream. Works today with no
   cooperation from the lab. Sufficient, because synchronisation is offline
   anyway.
2. **Log tailing.** Follow the file as it is written, emit new lines as samples.
   Adds live display. Beware flush buffering; arrival timing is not meaningful,
   only the log's own timestamp column is.
3. **REST.** If and when the lab's extension exists.

**Open question to resolve with the lab before this is built:** what the log's
timestamp column actually is — wall clock, seconds since simulation start, or a
frame counter — and whether it is anchored to anything absolute. This determines
how SCANeR ties to the other clocks. Sample data shows median 10 ms spacing with
labels in whole milliseconds and irregular gaps (~60% land exactly on 10 ms), so
the reference axis is the simulator's actual marks, never a synthetic 100 Hz grid.

---

## Replay adapter

Reads a recorded fixture from `fixtures/` and emits it at the correct rates as if
it were live hardware, including burst structure for BITalino. Implements the
same interface. This is what makes the whole pipeline developable and testable
with no hardware attached, and what the sync tests run against.

Supports a speed multiplier (`1.0` for realistic timing, higher for fast tests)
and a seek offset.

---

## Reference stream

The sync module takes a `reference_stream` identifier from configuration.
Everything else is aligned onto that stream's timestamps. **Nothing in the sync
module names a specific device.**

SCANeR is the intended reference. Until the SCANeR adapter exists, Tobii is the
interim reference — a legitimate choice, since it is NTP-synced and carries
per-sample timestamps. Swapping is a config change plus a re-run of the post-stop
job. The chosen reference is recorded in each take's manifest so recordings are
self-describing.

The reference axis must never be assumed regular. Both candidate references are
irregular.
