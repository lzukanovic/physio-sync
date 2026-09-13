# Task 01 — The spine, on the replay adapter

Branch: `phase/01-spine`. Requires Phase 0 merged.

Read `CLAUDE.md`, `docs/adapters.md` (all of it), `docs/data-model.md`, and the
"Shape" section of `docs/architecture.md`.

**No real device code in this task.** The only adapter implemented is the replay
adapter. This is deliberate: the whole capture pipeline gets built and tested
without hardware, and the fixture becomes the regression test for everything that
follows.

## Scope

1. **Fixture preparation.** `fixtures/sample-session/` holds a trimmed excerpt of
   the lab's real recording: Tobii gaze, Tobii IMU, SCANeR telemetry, BITalino.
   Keep it small enough to commit (a couple of minutes). Write
   `fixtures/README.md` recording its provenance and what was trimmed.

2. **Replay adapter** implementing `SourceAdapter`. Reads the fixture and emits
   batches at realistic wall-clock rates. Must reproduce **BITalino burst
   structure** (several samples arriving nearly simultaneously, then a gap) —
   flat emission would hide the exact problem the platform exists to solve.
   Supports a speed multiplier and a seek offset. Registered as
   `replay:<stream>`.

3. **Session manager.** Start, stop, cancel. Owns adapter lifecycles. Records
   `t_start` and `t_stop` as host wall-clock. Creates the take directory, writes
   the manifest incrementally, finalises on stop. Cancel deletes the directory.
   Must be safe to stop at any point, including mid-batch.

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
   recording indicator, one scrolling live chart showing a 20-second window, and
   a sample counter per stream. Function over appearance — the designed screens
   come in Phase 4.

8. **Golden-file test.** Run a replay session at high speed, assert the written
   JSONL matches the fixture sample-for-sample, and assert the manifest has
   correct coverage intervals and sample counts. This test runs in CI with no
   hardware.

## Out of scope

Real devices, Parquet conversion, sync, exports, DuckDB, study management,
playback, styling.

## Done when

- `python -m physiosync` then starting a replay session produces a take
  directory with complete JSONL and a valid manifest.
- The live chart updates smoothly and the drop counter is visible and non-fatal.
- The golden-file test passes.
- Cancelling mid-session leaves nothing behind.
- Stopping with the browser closed still finalises the take correctly.

## Watch for

The most likely failure here is the decimator being wired in series with the
writers, so that a slow WebSocket client stalls disk writes. Verify explicitly:
run a session with no client connected, and with a deliberately slow client, and
confirm the JSONL is identical.
