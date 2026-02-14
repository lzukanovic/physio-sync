# physio-sync

Platform for capturing and synchronizing physiological sensor data.

## Tech Stack

- **Collector**: Python 3.10, asyncio (runs on host, not Docker)
- **API**: Python 3.12, FastAPI, SQLAlchemy, Alembic (Docker)
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS (Docker)
- **Database**: TimescaleDB (PostgreSQL 16 + timescaledb extension) (Docker)

## Project Structure

- `services/collector/` — Sensor data collection (host process)
- `services/api/` — REST + WebSocket API
- `services/web/` — Web frontend
- `db/` — Database initialization scripts

## Conventions

- Collector uses the **adapter pattern**: each sensor implements `BaseAdapter`
- All timestamps are normalized to **microseconds since epoch (UTC)**
- Collector streams data to API via WebSocket
- API uses async SQLAlchemy with asyncpg
- Frontend uses Next.js App Router (not Pages Router)

## Sensor Notes

- **BITalino**: PLUX binaries bundled (Apache 2.0). Uses callback-based `onRawFrame`.
- **Tobii Pro SDK**: NOT bundled (non-commercial research license). Must be installed separately. Adapter fails gracefully if missing.
- **SCANeR**: Placeholder adapter, implementation deferred.

## Key Commands

```bash
# Start infrastructure
docker compose up -d

# Start collector (from services/collector/)
python -m collector.main

# Run API tests
docker compose exec api pytest

# Run collector tests (from services/collector/)
pytest
```
