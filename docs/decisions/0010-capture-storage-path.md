# 0010 — Capture storage path: one writer thread, unbounded queue, one JSON line per sample

**Context.** Every sample must reach disk unmodified, and nothing downstream may
back-pressure an adapter (ADR 0006). The PLUX callback runs on a foreign thread;
other adapters run on the event loop. A crash should cost seconds, not the take,
and a closed capture file must never be rewritten.

**Decision.** The `SampleSink` handed to adapters is `Writer.put`, which appends
to an unbounded `queue.SimpleQueue` and returns. One thread per take drains the
queue into one gzipped JSONL file per stream (`raw/<stream id>.jsonl.gz`), one
JSON object per sample, keys in `StreamSpec.columns` order. At most every second
it sync-flushes the gzip stream and fsyncs. Files are opened exclusive-create
(`"xb"`). The decimator (Task 01, item 5) will be a second consumer called from
the same sink, never in series with the writer.

**Consequences.** `put` cannot block or drop; the queue is bounded only by memory,
which grows only if the disk stalls (the disk guard is Phase 6). A file cut off
by a crash decodes up to its last flush. `json.dumps` writes floats with `repr`,
so float64 timestamps round-trip exactly and the golden-file test compares for
equality. A line per batch would be smaller but would record batch boundaries,
which follow the host timer (ADR 0009) and carry no information. The compressed
bytes depend on when flushes fell, so two captures of the same data are compared
decompressed, never byte-for-byte.
