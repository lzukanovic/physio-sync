# physio-sync

A platform for capturing and synchronising time-series data from heterogeneous
sensor systems used in driving-simulation research.

Researchers running simulator studies currently record each device with its own
vendor software — Tobii Pro Glasses 3 Controller, OpenSignals for BITalino, the
simulator's own logs — and align the resulting files by hand afterwards. That is
slow and error-prone. This platform consolidates the whole workflow into one
tool: connect the devices, configure them, record, watch the live data to confirm
capture is working, and afterwards review, align and export the result.

It runs locally on the single machine that interfaces with all the sensors.

Developed as a master's thesis project at the Faculty of Computer and Information
Science, University of Ljubljana, for use in the faculty's driving simulator
laboratory.

## Supported sources

| Source              | Connection                                    | Notes                                                                                  |
| ------------------- | --------------------------------------------- | -------------------------------------------------------------------------------------- |
| BITalino            | Bluetooth, PLUX Python SDK                    | No device clock; timestamps reconstructed from the sample sequence number              |
| Tobii Pro Glasses 3 | Ethernet / WiFi, HTTP + WebSocket via g3pylib | Gaze, IMU, live scene video; NTP-synchronised device clock                             |
| SCANeR              | Simulator log file (REST planned)             | The intended synchronisation reference                                                 |
| Replay              | —                                             | Plays back a recorded session as if it were live hardware, for development and testing |

Adding a source means implementing one interface. No source depends on any other
being present.

## What it does

- **Capture.** All configured devices recorded together into one session,
  organised as Study → Participant × Scenario → Recording → Take.
- **Monitor.** Live plots and device status during capture so the operator can
  confirm everything is being recorded before the participant finishes.
- **Synchronise.** After each recording, every stream is aligned onto a
  configurable reference stream's timeline, with a per-recording quality report
  covering sample loss, gaps, clock offset and measured sampling rates.
- **Review.** Browse recorded data with zoom, pan and channel selection.
- **Export.** Parquet or CSV, synchronised onto the common axis or raw per
  stream.

## Status

Early development. See [`docs/plan.md`](docs/plan.md) for the phased build plan
and current position.

## Documentation

| Document                                       | Contents                                           |
| ---------------------------------------------- | -------------------------------------------------- |
| [`docs/architecture.md`](docs/architecture.md) | Stack, repository layout, data flow, deployment    |
| [`docs/data-model.md`](docs/data-model.md)     | Entities, on-disk format, manifest, quality report |
| [`docs/adapters.md`](docs/adapters.md)         | The source interface and per-device timing rules   |
| [`docs/plan.md`](docs/plan.md)                 | Build phases and open questions                    |
| [`docs/decisions/`](docs/decisions/)           | Architecture decision records                      |
| [`CLAUDE.md`](CLAUDE.md)                       | Working conventions and project invariants         |

## Requirements

- **Python 3.10 exactly.** Forced by the PLUX binaries, which are compiled per
  Python minor version and are not published for 3.11 or 3.12 on Windows. See
  [`CLAUDE.md`](CLAUDE.md).
- Node.js 22+ for frontend development only. Not needed to run the application;
  the frontend is built ahead of time and shipped inside the Python package.
- Chrome, for the WebRTC live video preview.

## Development

The Python environment is managed with conda.

```bash
conda activate physio_sync_env
pip install -e ".[dev]"
export PHYSIOSYNC_DATA=~/physiosync-data     # set PHYSIOSYNC_DATA=... on Windows
python -m physiosync                          # API + UI on http://localhost:8000

npm --prefix web install
npm --prefix web run dev                      # frontend with hot reload, proxies to :8000
npm --prefix web run build                    # build into src/physiosync/web/

pytest                                        # runs against fixtures/, no hardware needed
python -m physiosync.devcheck bitalino        # connect one device and print samples
```

Recorded data lives entirely under `$PHYSIOSYNC_DATA`, outside the installation,
so upgrading never touches it.

## Related repositories

Two earlier prototypes, used to validate device connectivity and to establish the
timing behaviour documented in `docs/adapters.md`:

- [`bitalino-mvp`](https://github.com/lzukanovic/bitalino-mvp)
- [`tobii-mvp`](https://github.com/lzukanovic/tobii-mvp)

## Licence

MIT, see [LICENSE](LICENSE).

Bundled PLUX API binaries are distributed under the Apache License 2.0 by PLUX
Biosignals. The Tobii Pro Glasses 3 API is subject to the Tobii Pro Software
Development License Agreement for Research Use.
