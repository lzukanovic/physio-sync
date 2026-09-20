# 0006 — `SampleSink` is synchronous, non-blocking and thread-safe

**Context.** Adapters hand sample batches to the capture path through a
`SampleSink`. The PLUX SDK delivers frames on a thread it owns, while the Tobii
and SCANeR adapters run as asyncio tasks. The storage path must never be
back-pressured by anything downstream (see `docs/architecture.md`).

**Decision.** `SampleSink` is a plain callable, `sink(batch) -> None`. It is
synchronous, must not block, must not raise into the adapter, and is safe to call
from any thread. `SampleBatch` is a columnar, frozen dataclass rather than a
Pydantic model, since one is built per device callback.

**Consequences.** The BITalino callback can call the sink directly with no
event-loop hand-off. Overflow policy lives in the sink implementation (Phase 1,
queue in front of the writers), not in the adapters. An `async` sink would have
forced every SDK-thread adapter to bridge into the loop and made a slow writer
able to stall capture.
