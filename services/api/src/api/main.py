"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.db.session import engine
from api.models import Base
from api.routers import data, devices, export, recordings
from api.ws.handlers import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (Alembic handles migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="physio-sync API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(recordings.router, prefix="/api/recordings", tags=["recordings"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
