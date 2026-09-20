# Task 00 — Contracts

Branch: `phase/00-contracts`

Read `CLAUDE.md`, `docs/architecture.md`, `docs/data-model.md`, and the
"Contract" section of `docs/adapters.md` before planning.

**No device code in this task. No capture logic. No charts.** This task creates
the shapes that later tasks fill in.

## Scope

1. **Project layout.** As specified in `docs/architecture.md` → Repository
   layout. `src/` layout, package name `physiosync`. Create the sub-packages
   (`api`, `adapters`, `capture`, `store`, `sync`, `export`) with `__init__.py`
   only; later tasks fill them. `src/physiosync/vendor/PLUX-API-Python3/` may
   already contain binaries — leave them alone, but ensure `pyproject.toml`
   declares them as package data and `.gitignore` does not exclude `*.dll`,
   `*.pyd`, or `*.so` under that path.

2. **`pyproject.toml`** pinned to `requires-python = "==3.10.*"`. This is forced,
   not a preference: PLUX ships no Win64 binary for 3.11 or 3.12, and g3pylib
   supports up to 3.12 via the lab's fork, so 3.10 is the only version where both
   work on Windows. **Do not bump it, and do not widen the constraint.**

   Dependencies: fastapi, uvicorn, pydantic, duckdb, pyarrow, and g3pylib pinned
   by commit (URL in `CLAUDE.md`) — its transitive deps come with it. Dev: pytest,
   ruff. Nothing else without asking.

3. **Config** from environment with defaults. `PHYSIOSYNC_DATA` (required),
   `PHYSIOSYNC_PORT` (8000), `PHYSIOSYNC_REFERENCE_STREAM`. Fail loudly with a
   clear message if the data root is unset or unwritable.

4. **SQLite schema and migrations** for the entities in `docs/data-model.md`.
   Plain SQL migration files applied on startup; no ORM, no Alembic. Sample data
   never goes in SQLite.

5. **`SourceAdapter` protocol** in `adapters/base.py`, exactly as specified in
   `docs/adapters.md`, with `StreamSpec`, `SampleBatch`, `SampleSink`,
   `DeviceStatus`, `StreamEpochs`, `StopInfo` as typed dataclasses or Pydantic
   models. Types and docstrings only — no implementations.

6. **Manifest model** matching `docs/data-model.md`, with read and write helpers
   and a round-trip test.

7. **FastAPI app.** `/api/health` returning version, data root, and whether the
   DB is reachable. Mount the built frontend at `/` with SPA fallback so a
   refresh on a client route does not 404. API and WebSocket routes mounted
   before the catch-all.

8. **Vite + React + React Router shell.** Three empty routes (`/studies`,
   `/takes/:id`, `/devices`), a layout with a sidebar, and one call to
   `/api/health` displayed on screen. No styling system decisions yet beyond
   picking one — say which in the plan.

9. **`python -m physiosync`** runs uvicorn on the configured port bound to
   `127.0.0.1`.

10. **Dev proxy** so `npm run dev` proxies `/api` and `/ws` to `:8000`.

## Out of scope

Adapters, capture, charts, DuckDB queries, exports, auth, Docker, CI.

## Environment

Conda, environment `mag_env`, already created. `conda activate mag_env` then
`pip install -e ".[dev]"`. Do not create a venv and do not change the
environment's Python version.

## Done when

- `python -m physiosync` serves the SPA and the health value renders in the browser.
- `npm --prefix web run build` output is served by the Python process.
- `pytest` passes, including the manifest round-trip test.
- A fresh clone with `PHYSIOSYNC_DATA` set to an empty directory starts and
  creates the database.

## Also produce

ADRs in `docs/decisions/`: single process, DuckDB + Parquet, React + Vite over
Next, no Docker on Windows because of Bluetooth. Four or five sentences each:
context, decision, consequences.
