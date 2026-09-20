# Build plan

Ordering principle: lab access is the scarce resource, not calendar time. Build
in the order that makes a real measurement session possible, then everything else.

Each phase is one branch and a small number of Claude Code sessions, driven by
the task file in `docs/tasks/`. A phase is not done until its verification
command runs clean.

---

## Phase 0 — Contracts

No device code, no features. Establish what every later session conforms to.

Repo layout, `pyproject.toml` pinned to Python 3.10, SQLite schema and
migrations, the `SourceAdapter` protocol as types, on-disk layout and manifest
schema, Vite + React shell with routing and a `/api/health` call, FastAPI serving
the built frontend.

**Done when:** `python -m physiosync` serves the SPA at `:8000`, the health
endpoint responds through it, and `pytest` runs (even with few tests).

## Phase 1 — The spine, on the replay adapter

The highest-leverage phase. Build the entire capture pipeline against recorded
data so it is developable and testable with no hardware.

Replay adapter reading `fixtures/`. Session manager (start/stop/cancel). JSONL
writers, one per stream. Manifest written incrementally. Decimator and the live
WebSocket feed. Minimal UI: start/stop plus one live chart.

**Done when:** starting a replay session writes complete JSONL files and a valid
manifest, the UI chart updates smoothly, and a golden-file test asserts the
written output matches the fixture.

## Phase 2 — Real adapters

One adapter per session, one branch each. Each is verified with
`python -m physiosync.devcheck <device>` against real hardware.

**2a — BITalino.** Vendor the PLUX binaries for Python 3.10 only (`Win64_310`
plus one Mac folder) into `src/physiosync/vendor/`. Port the binary loader
from the MVP with the path and error-handling fixes in `docs/adapters.md`. Three
timestamp columns. `nSeq` continuity assertion. Settle by measurement whether
`nSeq` wraps.

**2b — Tobii.** Via g3pylib. Discovery (Zeroconf, mDNS, AP address, manual). Gaze
and IMU, storing `device_ts` and `local_ts`. NTP check and warning tag.
`system.time` at start and stop. `recorder!start`/`stop` on the device. WebRTC
live preview. Calibration workflow.

**2c — SCANeR.** Post-hoc log import first. Blocked on specifics from the lab;
does not block any other phase.

**Done when:** each adapter captures 5 minutes to disk with a correct manifest
and no unexplained gaps.

## Phase 3 — Post-stop job, sync, export

Runs on stop. JSONL to Parquet. Derived columns (`t_endanchored` for BITalino).
Tobii epoch derivation. Download of the small device-side Tobii files.
Alignment of every stream onto `reference_stream`. Quality report. Export
endpoints: Parquet and CSV, synced and raw, full axis and trimmed.

Reference: `../EDA-Bitalino-Tobii-Example-2/make_all_figures.py`. That script
was run and produced the figures in the thesis, and it is the source of every
measured number in `docs/adapters.md`. Port its loaders, offset computation and
rate statistics rather than rewriting them; the quality report is largely the
same calculations in a different output format.

Ignore the `.ipynb` files and `sync.json` in that directory — generated, never
run, unknown provenance. The thesis's synchronisation chapter supplies the method
choice per stream and why each alternative was rejected; `make_all_figures.py`
supplies the working code.

**Done when:** a replayed fixture produces `synced.parquet` whose alignment
matches the analysis script's output within tolerance, and both export formats
round-trip correctly.

## Phase 4 — Study management and screens

Studies, participants (with CSV import), scenarios, recordings, takes, canonical
marking. Screens 01 Studies list, 02 Study detail, 03 Recording (live) from the
existing design. Device management screen and Tobii calibration UI.

## Phase 5 — Playback and raw-data explorer

The DuckDB range/aggregate endpoint. Zoom and pan across a full recording,
channel selection, multiple synchronised panes, annotations. Take list with the
canonical one marked.

Video playback is deferred to the end of this phase: download the scene mp4 from
the glasses in the post-stop job and scrub it against the time series. Everything
needed for it is already in place by then.

## Phase 6 — Hardening

30-minute unattended run. Bluetooth disconnect and reconnect. Periodic flush so a
crash costs seconds, not the take. Disk space guard. Windows specifics: disable
sleep and USB selective suspend. Packaging and the lab install procedure.

---

## Open items blocking nothing but worth chasing

- **Fork g3pylib to `lzukanovic`** and repoint the pin. The project currently
  depends on `simp16/glasses3-pylib` at a single commit — one person's account,
  and the entire Tobii path rests on it. Same commit, own remote. Do before the
  first real measurement session.
- SCANeR: what its log's timestamp column is, and whether a REST extension exists.
- Whether `nSeq` wraps under the PLUX SDK (settle in 2a by measurement).
- Whether Tobii device clock and host clock agree on the length of a second over
  a long capture — decides whether the epoch is a constant or a linear fit.
  Requires one 10-minute capture.
