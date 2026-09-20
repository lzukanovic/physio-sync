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

## Keeping these docs current

`docs/` describes intent, written before most of the code existed and partly from
documentation rather than measurement. **It will be wrong in places.** When
development or the reference material below contradicts a document, update the
document in the same commit as the code. Stale docs are worse than no docs.

Two exceptions, where the answer is to propose rather than edit:

- The **Prohibitions** below are settled decisions with reasoning recorded in
  `docs/decisions/`. If one turns out to be wrong, say so and explain why, then
  wait. If accepted, write a **new** ADR superseding the old one; never silently
  rewrite an existing ADR, since the record of what was believed and when is
  itself thesis material.
- Anything stated as **measured** (sampling rates, epoch behaviour, timestamp
  formats) must not be changed on the basis of documentation or inference. Change
  it only against an actual capture, and say which one.

Everything else — tech details, data model fields, adapter specifics, task
briefs, this file — is fair game to edit as you learn more.

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

The Python environment is conda, named `physio_sync_env`. Activate it before anything:

```
conda activate physio_sync_env

pip install -e ".[dev]"              # project itself, into the conda env
python -m physiosync                 # run the app (serves UI at :8000)
python -m physiosync.devcheck <dev>  # connect to one device, print samples, exit
pytest                               # tests, run against fixtures/ (no hardware)
npm --prefix web run dev             # frontend dev server, proxies /api to :8000
npm --prefix web run build           # build into src/physiosync/web/
```

Do not create a venv, do not run `uv`, do not change the Python version in the
environment. Python 3.10 is a hard constraint (see Invariants).

## Local reference material

This repository sits inside a thesis working directory alongside the prototypes
and the exploratory analysis. Those directories are **outside the repo**, so they
must be made readable with `/add-dir` (or `claude --add-dir ...`) before they can
be read. Paths below are relative to this repository's parent.

Read these rather than reinventing. They contain measured behaviour that the
documentation of these devices does not.

| Path                                                               | What is in it                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `../Bitalino/bitalino-mvp/`                                        | Working BITalino capture. `utils/plux_loader.py` is the per-platform binary loader — **port it**. `services/acquisition_service.py` has the threading model and frame callback.                                                                                                                                                                                                                        |
| `../Tobii/tobii-mvp/`                                              | Working Glasses 3 capture via g3pylib. `services/acquisition_service.py`, `services/async_bridge.py` (asyncio inside a sync app), `services/webrtc_signaling_service.py`, `static/js/webrtc.js`. Its recordings show the `DeviceTS`/`LocalTS` convention.                                                                                                                                              |
| `../Tobii/Tobii_Glasses_3_Developer_Guide.pdf`                     | The official API reference. Authoritative for endpoints, signals, and the timestamp semantics in `docs/adapters.md`.                                                                                                                                                                                                                                                                                   |
| `../EDA-Bitalino-Tobii-Example-2/make_all_figures.py` + `figures/` | **Verified.** The analysis script that was actually run, and the figures it produced for the thesis. It is the source of every measured number quoted in `docs/adapters.md` — stream start offsets, measured sampling rates, gap distributions. Its loaders and offset computation are the reference for Phase 3.                                                                                      |
| `../EDA-Bitalino-Tobii-Example-2/{bitalino,tobii,datalogger}/`     | **A complete real three-device session**, captured in an actual study and supplied by the project supervisor. BITalino (OpenSignals `.h5`/`.txt` plus a prototype CSV), Tobii (a full device-side recording folder and the scene video), and SCANeR (`datalogger/`, a full export). This is the source for `fixtures/` and the only ground truth available until the first capture with this platform. |
| `../Bitalino/Plux Python Samples/`                                 | Upstream PLUX examples, including scheduled and multi-device acquisition.                                                                                                                                                                                                                                                                                                                              |
| `../EDA-Bitalino-Tobii-Example/`                                   | An earlier, smaller sample: BITalino ECG and a Tobii gaze/IMU pair in the `DeviceTS`/`LocalTS` CSV format.                                                                                                                                                                                                                                                                                             |

**Do not treat `../EDA-Bitalino-Tobii-Example-2/*.ipynb` or `sync.json` as
reference.** The notebooks were generated and never run or verified, and
`sync.json` is of unknown provenance — possibly their output. Neither is evidence
of how the data behaves. `make_all_figures.py` in the same directory **is**
verified and is the one to read.

Both MVPs are Flask + Socket.IO prototypes. Their **device communication** is
proven and should be reused; their architecture is not the target and should not
be copied.

## Pinned external dependencies

- **g3pylib**, the Glasses 3 Python client, pinned by commit to the lab's fork
  which extends support past 3.10:
  `g3pylib @ git+https://github.com/simp16/glasses3-pylib.git@d25271aa62d92dcbe5420bd83a9c9319e2d980a7`
  Its transitive dependencies (aiortsp and others) arrive with it and are not
  subject to the no-new-dependency rule.
- **PLUX API Python3** binaries are vendored into
  `src/physiosync/vendor/PLUX-API-Python3/`, not installed — there is no PyPI
  distribution. Only the folders for Python 3.10 on the platforms actually used.
  See `docs/adapters.md`.

Repository layout is specified in `docs/architecture.md` → Repository layout.
`src/` layout; the package is `physiosync`, the repo is `physio-sync`.
