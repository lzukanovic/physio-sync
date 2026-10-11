# 0009 — Replay is per device, and rebases absolute columns by a constant shift

**Context.** The replay adapter plays `fixtures/live-capture/` as if it were live
hardware. Task 01 asked for `replay:<stream>` and for every stream to be rebased
onto session t=0. The two Tobii files are one session on one device clock (IMU
starts 0.21 s before gaze); BITalino was recorded on another day. The live
adapters write host-clock columns (`arrival_ts`, `local_ts`) from `time.time()`.

**Decision.** One replay adapter per device (`replay:bitalino`, `replay:tobii`),
emitting the live stream ids and columns. Each device is rebased from a single
origin, so streams sharing a device clock keep their relative offset. Relative
columns (`nseq`, `device_ts`) pass through unchanged. Absolute columns are the
recorded values plus one constant per device, chosen so the origin plus seek
maps to the replay's `t_start`; they are not taken from `time.time()`.

**Consequences.** Replayed output is deterministic and independent of speed, so
the golden-file test can compare it with the fixture. Burst structure and the
`local_ts − device_ts` spread survive, so the Tobii epoch derivation works on
replayed data as on live data. A per-stream rebase would have destroyed the
gaze/IMU offset. A replayed `arrival_ts` is what the arrival would have been at
1×, not the moment the sample reached the sink; at 1× the two agree to within a
timer tick, which `tests/test_replay.py` asserts.
