# physio-sync

A platform for capturing and synchronizing data from heterogeneous sensor systems for the measurement of physiological signals.

## Architecture

```
BITalino (Bluetooth) ──┐
Tobii Pro 3 (Network) ──┤── Collector (host) ──WebSocket──> API (Docker) ──> TimescaleDB (Docker)
SCANeR (Local/TBD) ─────┘                                       │
                                                                 │ REST + WebSocket
                                                                 ▼
                                                          Web Frontend (Docker)
```

### Services

| Service | Technology | Runs In |
|---------|-----------|---------|
| **collector** | Python 3.10, asyncio | Host (Bluetooth/hardware access) |
| **api** | Python 3.12, FastAPI | Docker |
| **web** | Next.js 15, React 19, TypeScript | Docker |
| **db** | TimescaleDB (PostgreSQL 16) | Docker |

The collector runs on the host machine because BITalino requires Bluetooth access and SCANeR is installed locally. The remaining services run in Docker.

## Prerequisites

- Docker & Docker Compose
- Python 3.10 (for collector)
- Node.js 22 (optional, for local frontend dev)
- BITalino device (Bluetooth)
- Tobii Pro Glasses 3 (network)

## Quick Start

### 1. Start infrastructure (DB, API, Web)

```bash
cp .env.example .env
# Edit .env with your device addresses and credentials
docker compose up -d
```

### 2. Start the collector (on host)

```bash
cd services/collector
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
python -m collector.main
```

### 3. Access the UI

- **Frontend**: http://localhost:3000
- **API docs**: http://localhost:8000/docs

## Sensor SDKs

### BITalino (PLUX API)

Platform binaries are bundled in `services/collector/PLUX-API-Python3/` (Apache License 2.0).

### Tobii Pro SDK

The Tobii Pro SDK is licensed for **non-commercial research use only** and cannot be bundled in this repository. Install it separately:

```bash
pip install tobii-research
```

See [Tobii Pro SDK documentation](https://developer.tobiipro.com/) for details.

## License

MIT - see [LICENSE](LICENSE).

PLUX API binaries: Apache License 2.0.
Tobii Pro SDK: separate non-commercial research license (not bundled).
