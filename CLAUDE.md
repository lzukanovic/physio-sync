# physio-sync

Platform for capturing and synchronising data from heterogeneous sensor systems
(BITalino, Tobii Pro Glasses 3, SCANeR driving simulator) in a driving-simulation
research lab. Master's thesis project. Runs on a single Windows PC in the lab.

**Read before working:** `docs/architecture.md` for the stack and why,
`docs/adapters.md` for device-specific timing rules, `docs/data-model.md` for
entities and on-disk layout, `docs/plan.md` for phases, `docs/tasks/` for the
brief covering the current phase.

## How to work in this repo

- One task file per session. Work only on the task you were pointed at.
- Start in plan mode. Present the plan before writing code.
- Do not touch two layers in one task. Adapter work does not touch the frontend.
- Every task ends with a command that can be run to verify it. State it.
- Record every non-obvious design choice as an ADR in `docs/decisions/`.

## Prohibitions

These are decisions already made. Do not revisit them without asking.

- **No external database server.** No Postgres, no TimescaleDB, no InfluxDB.
- **No Docker.** The lab PC is Windows; BITalino needs host Bluetooth access.
- **No Next.js, no server-side rendering, no Node on the lab PC.** React + Vite,
  built to static files, served by FastAPI.
- **No `tobii-research` package.** That is the SDK for screen-based trackers.
  Glasses 3 uses its own HTTP/WebSocket API.
- **Adapters never resample, interpolate, or filter.** They emit raw samples with
  the timestamps defined in `docs/adapters.md`. All alignment happens offline.
- **The live UI feed is lossy by design.** It is decimated and batched. It must
  never apply backpressure to the capture path.
- **No new dependency without asking.**
- **Never rewrite a capture file after it is closed.** Derived columns are
  computed in the post-stop job and written to new files.

## Invariants

- All absolute timestamps are UTC seconds as float64. Never naive local time.
- Every stream in a recording records its epoch and coverage interval.
- The synchronisation reference is configuration (`reference_stream`), not a
  hardcoded device. Nothing in the sync module names a specific device.
- **Python 3.10 exactly, on every machine.** Forced by the intersection of two
  dependencies: PLUX ships no Win64 binary for 3.11 or 3.12 (only 37, 38, 39,
  310, 313), and g3pylib supports up to 3.12 via the lab's fork. 3.10 is the only
  version where both work on Windows. Do not bump it.

## Commands

```
uv sync                              # or: pip install -e ".[dev]"
python -m physiosync                 # run the app (serves UI at :8000)
python -m physiosync.devcheck <dev>  # connect to one device, print samples, exit
pytest                               # tests, run against fixtures/ (no hardware)
npm --prefix web run dev             # frontend dev server, proxies /api to :8000
npm --prefix web run build           # build into physiosync/web/
```

## Prior art

Two prototypes exist and are the reference for device communication. Consult
them rather than reinventing:

- `lzukanovic/bitalino-mvp` — PLUX SDK usage, per-OS/per-Python binary loading,
  acquisition threading. **Port the binary loader verbatim.**
- `lzukanovic/tobii-mvp` — Glasses 3 discovery, WebSocket signals, sample parsing,
  the `DeviceTS`/`LocalTS` two-column CSV convention.

## Pinned external dependencies

- **g3pylib**, the Glasses 3 Python client, pinned by commit to the lab's fork
  which extends support past 3.10:
  `g3pylib @ git+https://github.com/simp16/glasses3-pylib.git@d25271aa62d92dcbe5420bd83a9c9319e2d980a7`
  Its transitive dependencies (aiortsp and others) arrive with it and are not
  subject to the no-new-dependency rule.
- **PLUX API Python3** binaries are vendored into the repo, not installed. Only
  the folders for Python 3.10 on the platforms actually used. See
  `docs/adapters.md`.
