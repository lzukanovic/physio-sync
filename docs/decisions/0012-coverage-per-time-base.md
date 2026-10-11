# 0012 — Coverage per time base, and the wall-minus-monotonic delta

Amends the `coverage` field of ADR 0007.

**Context.** ADR 0007 gave each stream one nullable `coverage`, in UTC. For Tobii
that stays null until the post-stop job derives the epoch, so a manifest closed
at stop said nothing about how long Tobii recorded, and the golden-file test
could not check it. Separately, `plan.md` lists host wall-clock corrections
during a take as undetected: `arrival_ts`, `local_ts` and `t_start` all come from
`time.time()`.

**Decision.** Each stream records `coverage_local`, the first and last value of
its own time column (`StreamSpec.time_column`: `t` for BITalino, `device_ts` for
Tobii), always at stop; and `coverage_utc`, which equals `coverage_local` when
that column is already UTC (`StreamSpec.time_is_utc`) and is `epoch_utc` plus it
otherwise, so null until the epoch is known. Nothing special-cases a device.

The take records `wall_monotonic_delta = [start, stop]`, each
`time.time() − time.monotonic()`. It is named for what it is because only
`stop − start` means anything — the wall-clock step or slew during the take — and
an absolute "offset" would invite reading it against NTP. Flagging lands in the
Phase 3 quality report; sampling it periodically as a stream waits for Phase 6
and only if needed.

**Consequences.** Every stream's extent is in the manifest at stop, in the time
base it was recorded in. `usable_window` is the intersection of `coverage_utc`.
Start/stop readings detect a step but not when it happened.
