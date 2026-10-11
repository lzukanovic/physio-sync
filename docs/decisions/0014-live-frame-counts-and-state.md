# 0014 — Live frame carries true sample counts and the take start; UI shows server state only

Extends the frame of ADR 0013; does not change its topology.

**Context.** Task 01 item 7 needs a per-stream sample counter and an elapsed timer. The
0013 frame had neither. Counting the decimated samples a client receives gives ~20/s per
stream whatever the device rate, so a monitoring view whose job is "is everything capturing"
would read 20/s for a 130 Hz IMU. And a timer started from the client's own Start click does
not survive a reload or a second browser, which is exactly when an operator needs it.

**Decision.** Two fields in every frame:

- `received`: per stream, samples that reached `LiveFeed.put` since the take started.
  Counted under the lock `put` already takes; still O(1), still never blocks. It counts what
  the sink delivered, before any shedding, so `received - dropped` is what the display path
  kept. It is a live estimate: the authoritative count is the manifest's `n_samples`, written
  by the writer on stop.
- `t_start`: the take's `started_utc`, set by the session manager when it records it. Null
  between takes and in the instant between `reset` and the adapters starting.

**The UI derives recording state from the frame only, never from its own actions.** The
indicator says recording when the last frame said `recording: true`; while the WebSocket is
not connected it says "feed disconnected — state unknown" instead of keeping the last value.
An operator mid-session must never see "recording" because a button was clicked, or because
that was the last thing heard before the connection dropped. Phase 4 inherits this.

**Consequences.** The frame grows by two small dicts' worth. Nothing on the storage path
changes. The capture page is not load-bearing: a take is finalised by `POST
/api/session/stop` from anywhere, or on shutdown, with no browser open.
