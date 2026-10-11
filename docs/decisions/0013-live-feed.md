# 0013 — Live feed: fan-out at the sink, buffers bounded in stream time

**Context.** The display path (`docs/architecture.md` → Shape) must decimate to
10–20 Hz, drop freely under load, and never back-pressure the storage path. ADR
0010 made `Writer.put` the sink and reserved a second consumer on the same sink
for the decimator. Streams run at different rates (BITalino 100 Hz, Tobii gaze
~100 Hz, IMU ~130 Hz), and the replay adapter can run them at many times real
time.

**Decision.** Topology, as arrows:

```
adapter ──sink(batch)──┬──> Writer.put ──> unbounded queue ──> writer thread ──> raw/*.jsonl.gz
                       └──> LiveFeed.put ──> per-stream buffer (2 s, drop-oldest)
                                               ──> 10 Hz drain, decimate to ≤ 20 Hz
                                               ──> per-client queue (20 frames, drop-oldest)
                                               ──> /ws/live
```

The session's sink calls `writer.put` then `live.put`. Nothing on the storage
path reads from the live feed. `LiveFeed.put` runs on the adapter's call stack
(possibly a vendor SDK thread), so it only appends under an uncontended lock,
evicts, and returns; it never awaits, does no I/O, and never raises.

- **Input buffer bound is in the stream's own time** (`StreamSpec.time_column`),
  not host arrival time: whole batches are evicted from the front while they end
  more than 2 s before the newest sample. That caps memory at ~2 s of samples
  per stream whatever the replay speed; an arrival-time bound would hold
  2 s × speed of signal (≈ 660k samples at 1000×) if the drain stalled. At 1×
  the two are the same.
- **Decimation** keeps a sample once its own clock is ≥ 50 ms past the last kept
  one, so BITalino's bursts do not alias. Samples skipped by decimation are not
  drops.
- **Per-client queue** of 20 frames at 10 Hz, also 2 s. A slow client only fills
  its own queue; the drain never awaits a send. A new connection starts empty:
  current data, no backlog.
- **Counts.** Each frame carries `dropped` (samples shed from the input buffers,
  per stream, cumulative since the take started, so a client that skipped frames
  still sees true totals) and `skipped` (frames this client missed).
- **Batches are immutable after the sink call.** Writer and live feed receive the
  same `SampleBatch` object; the writer serialises it later on its own thread.
  The live feed only reads it. Slicing or mutating its columns in place would
  corrupt what lands on disk.

**Consequences.** At high replay speed the drop counts are large: the 10 Hz drain
genuinely cannot keep up with 50× data inside a 2 s window. That is correct
behaviour, and the counts show the shedding is confined to the display path while
the takes stay complete.

**The live view deliberately does not align streams; alignment is Phase 3's
job.** Frames carry each stream's own time column, and those are not comparable:
BITalino `t` is reconstructed host wall-clock, Tobii `device_ts` is seconds since
the stream opened. A shared axis would look like alignment and not be. So the UI
(Task 01 item 7) draws each stream in its own pane with its own time axis, and
the frame carries no common host-clock stamp. If a shared axis is ever wanted, it
needs a display-only host stamp per stream, labelled as such.

The topology test (`tests/test_live.py`) runs an in-process slow subscriber, not a
real WebSocket client with full TCP buffers: `TestClient`'s WebSocket buffers
without limit and cannot produce backpressure. A stalled `send` blocks only that
client's handler task by construction.

**Testing the topology by wall time fails against the replay adapter**, and only
against it. The replay emits everything due as one uncapped batch, so a stall in
the sink makes later batches bigger rather than the run longer: a 20 ms stall per
`put` with a client connected left wall time unchanged at 50× (measured: 4.29 s
vs 4.34 s). Capping the replay's batch size to make that test work was rejected:
it would change adapter behaviour for a test and contradict ADRs 0009 and 0010.
Instead the test stalls a client 0.5 s per frame and times every `live.put`: the
healthy max is ~30 µs (measured, macOS, 50×), the assertion is < 1 ms, and a
simulated 2 ms in-series wait fails it at ~6.7 ms. Content equality and the drop
counts are asserted alongside.

A real device has no catch-up: BITalino produces at 100 Hz whatever happens
downstream, so there a stalled sink would delay the writers and show in wall
time. Re-run the wall-time comparison against real hardware in Phase 2a.
