# Task 01 — The spine, on the replay adapter

Branch: `task/01-spine`. Requires Phase 0 merged.

Read `CLAUDE.md`, `docs/adapters.md` (all of it), `docs/data-model.md`, the
"Shape" section of `docs/architecture.md`, and `fixtures/README.md`.

**No real device code in this task.** The only adapter implemented is the replay
adapter. This is deliberate: the whole capture pipeline gets built and tested
without hardware, and the fixture becomes the regression test for everything that
follows.

## Environment

`conda activate mag_env`. Do not create a venv and do not change the
environment's Python version.

## Scope

1. **Fixture.** `fixtures/live-capture/` is **prepared before this task starts**
   and is an input, not something to create. It holds `bitalino.csv`,
   `tobii_gaze.csv` and `tobii_imu.csv`, 180 seconds each, in the format the
   prototype apps produce — which is the format a live stream produces.

   Read `fixtures/README.md` before planning around it. In particular: the three
   streams are **not** mutually synchronised, and this fixture must not be used
   for anything about cross-device alignment. If it is missing, stop and say so
   rather than substituting or generating data.

   `fixtures/study-session/` does not exist yet and is not needed here.

2. **Replay adapter** implementing `SourceAdapter`. Reads
   `fixtures/live-capture/` and emits batches at realistic wall-clock rates,
   pacing each stream from its own recorded inter-sample intervals.
   - Pace BITalino from its `Timestamp` column, **not** from the nominal 100 Hz.
     The burst structure (~3.3 samples arriving ~1.27 ms apart, then ~30 ms of
     silence) is the phenomenon this fixture exists to carry.
   - Pace Tobii from `DeviceTS`.
   - Rebase every stream onto session t=0, so the three play together despite
     having been recorded separately.
   - Support a speed multiplier (1.0 realistic, higher for fast tests) and a
     seek offset.
   - Accept a directory path, so it can also be pointed at data generated later
     for long runs or fault injection.
   - Registered as `replay:<stream>`.

3. **Session manager.** Start, stop, cancel. Owns adapter lifecycles. Records
   `t_start` and `t_stop` as host wall-clock. Creates the take directory, writes
   the manifest incrementally, finalises it on stop. Cancel deletes the
   directory. Must be safe to stop at any point, including mid-batch.

4. **Writers.** One gzipped JSONL file per stream under `raw/`. Append-only.
   Flush at least every 2 seconds so a crash costs seconds, not the take. Never
   rewrite a closed file.

5. **Decimator and live feed.** A separate consumer of each adapter's output,
   reducing to 10–20 Hz per stream and batching for the WebSocket. **It must
   drop samples freely under load and must never apply backpressure to the
   writers.** Implement this as an explicit bounded queue with a drop-oldest
   policy, not as an accident of timing. Count drops and expose the count.

6. **WebSocket endpoint** `/ws/live` streaming decimated batches with stream IDs
   and timestamps. Reconnect cleanly; a reconnecting client gets current data,
   not backlog.

7. **Minimal UI.** One page: start/stop/cancel, elapsed timer, an unambiguous
   recording indicator, one scrolling live chart showing a 20-second window, a
   sample counter per stream, and the decimator's drop count. Function over
   appearance — the designed screens come in Phase 4.

8. **Golden-file test.** Run a replay session at high speed and assert:
   - the written JSONL contains exactly the fixture's samples, in order;
   - every stream's timestamps are **strictly increasing** in the output;
   - BITalino `Sequence` advances by exactly 1 throughout;
   - the manifest has correct coverage intervals and sample counts.

   Runs in CI with no hardware.

## Out of scope

Real devices, Parquet conversion, synchronisation, exports, DuckDB, study
management, playback, styling.

## Done when

- `python -m physiosync`, then starting a replay session, produces a take
  directory with complete JSONL and a valid manifest.
- The live chart updates smoothly and the drop counter is visible and non-fatal.
- The golden-file test passes.
- Cancelling mid-session leaves nothing behind.
- Stopping with the browser closed still finalises the take correctly.

## Watch for

**The decimator wired in series with the writers.** This is the most likely
failure: if a slow WebSocket client can stall disk writes, the design is wrong
even though everything appears to work. The decimator must be an independent
consumer with its own bounded queue. Verify explicitly — run a session with no
client connected, and again with a deliberately slow client, and confirm the
JSONL is byte-identical.

**Out-of-order samples.** Every stream's timestamps are strictly increasing in
the fixture and must be strictly increasing in what the writers emit. Assert it
rather than assuming it; an out-of-order sample is the failure that looks like
working code. A defect of exactly this kind was found and fixed in the fixture
itself during preparation (see `fixtures/README.md`).

**Scope creep into Phase 3.** The replay adapter reads CSV because that is what
the fixture is. It does not parse OpenSignals `.h5`, Tobii `.gz`, or SCANeR
exports — those belong to the post-stop job and the study-session importer.
