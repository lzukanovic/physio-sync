# 0002 — DuckDB over Parquet instead of a time-series database

**Context.** The UI needs zoom, pan, and channel selection across recordings up
to 30 minutes across several streams. The earlier scaffold chose TimescaleDB.

**Decision.** SQLite for entities. Parquet files on disk for samples. DuckDB,
embedded, as the query engine over those files. Chart queries use server-side
min/max-per-bucket aggregation so the client receives a bounded number of points
regardless of window size.

**Consequences.** No server process, no Docker, no ingest step. Storage format
and export format are the same artifact, readable from pandas, R, and MATLAB
without this platform existing. Concurrent multi-client writes are not supported,
which is acceptable for a single-operator lab tool.
