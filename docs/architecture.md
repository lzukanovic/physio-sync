# Architecture

## Shape

One Python process. Device adapters run in-process as asyncio tasks. FastAPI
serves the REST API, a WebSocket for the live monitoring feed, and the built
frontend as static files. Data lives in a directory outside the install.

```
  BITalino (Bluetooth) ─┐
  Tobii Glasses 3 (net) ─┼─ adapters ─┬─ writers ──> JSONL (capture)
  SCANeR (log / REST) ──┘             │                  │
                                      │           post-stop job
                                      │                  │
                                      │                  v
                                      │            Parquet + manifest
                                      │                  │
                                      └─ decimator       │  DuckDB
                                             │           │    │
                                          WebSocket   REST API │
                                             └────┬──────┴─────┘
                                                  v
                                          React SPA (static)
```

The two paths out of an adapter are deliberate and must stay separate:

- **Storage path.** Every sample, unmodified, appended to disk. Never blocked by
  anything downstream.
- **Display path.** Decimated to 10–20 Hz, batched, dropped freely under load.
  Monitoring only. Nothing depends on it being complete.

## Stack

| Layer          | Choice                                  | Why                                                                                 |
| -------------- | --------------------------------------- | ----------------------------------------------------------------------------------- |
| Backend        | Python 3.10, FastAPI, asyncio           | PLUX SDK is Python-only and ships per-version binaries                              |
| Entities       | SQLite                                  | Single file, no server, transactional, backs up by copying                          |
| Samples        | Parquet files on disk                   | Columnar, compressed, typed; readable by pandas/R/MATLAB without this platform      |
| Query          | DuckDB (embedded)                       | Queries Parquet directly, no ingest step; fast range + aggregate queries for charts |
| Capture format | gzipped JSONL                           | Append-only, crash-safe, converted to Parquet post-stop                             |
| Frontend       | React + Vite + React Router             | Multi-page structure without a full-stack framework to suppress                     |
| Serving        | FastAPI `StaticFiles` with SPA fallback | One process, one port, no Node on the lab PC                                        |

### Why not a time-series database

Considered and rejected. The dataset is small (a 30-minute session across three
devices is tens of MB in Parquet), always local, and never concurrently written
by multiple clients. A server-based TSDB would add an operational dependency on
a lab machine nobody administers, in exchange for capabilities that are not
needed. DuckDB over Parquet gives the query performance without the server, and
keeps the storage format identical to the export format. See
`docs/decisions/0002-duckdb-parquet.md`.

### Why one process

The capture path is where correctness matters most. A process boundary in the
middle of it buys deployment flexibility that is not needed today, in exchange
for serialisation, cross-process backpressure, two failure domains, and two logs
to correlate when a sample goes missing. The adapter interface is the seam where
a split would happen later, and it is maintained cleanly for that reason, but the
split is not built. See `docs/decisions/0001-single-process.md`.

## Repository layout

```
physio-sync/
├── CLAUDE.md  README.md  LICENSE  .gitignore  pyproject.toml
├── docs/                      architecture, data model, adapters, plan,
│   ├── decisions/             ADRs
│   └── tasks/                 one brief per phase
├── src/
│   └── physiosync/            the Python package (import physiosync)
│       ├── __main__.py        entry point: python -m physiosync
│       ├── config.py
│       ├── api/               FastAPI routes, WebSocket, static mount
│       ├── adapters/          one module per device + replay
│       ├── capture/           session manager, writers, decimator
│       ├── store/             SQLite access, migrations/, DuckDB queries
│       ├── sync/              alignment, epoch derivation, quality report
│       ├── export/            Parquet and CSV writers
│       ├── vendor/            third-party binaries (see below)
│       └── web/               BUILD OUTPUT — gitignored, filled by npm build
├── web/                       Vite + React source
├── fixtures/                  recorded sample session for the replay adapter
└── tests/
```

`src/` layout rather than a package at the repository root: it prevents importing
the source tree by accident instead of the installed package, so tests exercise
what the lab machine will actually run.

There is no top-level `db/`. The SQLite file lives in `$PHYSIOSYNC_DATA`, and its
migrations are package data under `src/physiosync/store/migrations/`.

### Vendored binaries

```
src/physiosync/vendor/PLUX-API-Python3/
├── README.md          # upstream source, version, commit, why these folders
├── Win64_310/         # lab machine
└── M1_310/            # development (or MacOS/Intel310)
```

The PLUX API ships compiled extension modules with no PyPI distribution, so they
are committed to the repo. Only the Python 3.10 folders for platforms actually in
use. `pyproject.toml` must declare these as package data so they land in the
wheel, and `.gitignore` must not exclude `*.dll`, `*.pyd`, or `*.so` under this
path.

g3pylib is **not** vendored. It is a pip dependency installed from a pinned git
commit.

## Chart queries

The frontend never receives raw sample arrays for long windows. It requests a
time range and a target point count; the backend runs a min/max-per-bucket
aggregation in DuckDB and returns a few thousand points regardless of window
size. This is what makes zoom and pan feel instant across a 30-minute recording.

```
GET /api/takes/{id}/series?streams=bitalino.A1,tobii.gaze2d_x
    &t0=120.0&t1=135.0&points=2000
```

Buckets are computed as `(t1 - t0) / points`; each bucket returns min, max, and
first value per channel. Below roughly 2000 samples in the window, return raw
points instead of aggregating.

## Export

Two formats, both derived from the same Parquet files:

- **Parquet** — the native format. No conversion, direct file copy.
- **CSV** — for Excel, MATLAB, and anyone who does not want Parquet. Written with
  a commented metadata header (take UUID, study, participant, scenario,
  reference stream, epochs, app version, export timestamp) in the style the
  existing MVPs already use, so an exported file is self-describing.

Both offered in two variants: **synced** (all streams on the reference axis, one
row per reference timestamp) and **raw per-stream** (each stream at its native
rate, its own file). Both offered over the full reference axis or trimmed to the
usable window (see `docs/data-model.md`).

CSV of a synced 30-minute recording is large but not unreasonable; stream it from
the endpoint rather than building it in memory.

## Deployment

Frontend is built on the developer machine into `src/physiosync/web/` (gitignored) and
included in the wheel as package data.
The lab PC gets Python 3.10, a plain venv, and a wheel — conda is the development
environment, not the deployment one; the lab machine should have as little
installed on it as possible. Started by a batch file that
opens the browser and runs `python -m physiosync`, bound to `127.0.0.1`. Data
root comes from `PHYSIOSYNC_DATA` and is never inside the install directory, so
upgrading is `pip install` of a new wheel and nothing else.

Chrome is the supported browser (WebRTC support for the Tobii live preview).
