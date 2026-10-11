"""FastAPI app: API routes first, then the built SPA as a catch-all."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from physiosync import __version__
from physiosync.capture.live import LiveFeed
from physiosync.capture.session import SessionError, SessionManager
from physiosync.config import Settings
from physiosync.store import db

log = logging.getLogger("physiosync")

DEFAULT_WEB_DIR = Path(__file__).resolve().parents[1] / "web"


class SPAStaticFiles(StaticFiles):
    """Serve index.html for client routes so a refresh on /takes/abc does not 404.

    Never for /api and /ws (an unknown API path must stay a 404), and never for paths
    that look like files (a missing /assets/x.js is a real 404).
    """

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            first, _, _ = path.partition("/")
            if e.status_code != 404 or first in ("api", "ws") or "." in path.rsplit("/", 1)[-1]:
                raise
            return await super().get_response("index.html", scope)


def create_app(settings: Settings, web_dir: Path = DEFAULT_WEB_DIR) -> FastAPI:
    live = LiveFeed()
    session = SessionManager(settings.data_root, settings.reference_stream, live=live)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = db.connect(settings.db_path)
        try:
            db.migrate(conn)
        finally:
            conn.close()
        feed = asyncio.create_task(live.run())
        try:
            yield
        finally:
            if session.recording:  # shutting down mid-take: finalise it, do not abandon it
                await session.stop()
            feed.cancel()
            with suppress(asyncio.CancelledError):
                await feed

    app = FastAPI(title="physio-sync", version=__version__, lifespan=lifespan)

    @app.get("/api/health")
    def health() -> dict:
        try:
            conn = db.connect(settings.db_path)
            try:
                conn.execute("SELECT 1").fetchone()
            finally:
                conn.close()
            db_ok = True
        except Exception:
            log.exception("health: database unreachable")
            db_ok = False
        return {"version": __version__, "data_root": str(settings.data_root), "db_ok": db_ok}

    @app.exception_handler(SessionError)
    async def session_error(request, e: SessionError):
        return JSONResponse({"detail": str(e)}, status_code=409)

    @app.post("/api/session/start")
    async def session_start(configs: Annotated[dict[str, dict], Body()]) -> dict:
        """Body: adapter id -> its configure dict, e.g. ``{"replay:bitalino": {"speed": 1}}``."""
        try:
            take = await session.start(configs)
        except ValueError as e:  # adapter refused its configuration
            return JSONResponse({"detail": str(e)}, status_code=400)
        return {"take": take.name}

    @app.post("/api/session/stop")
    async def session_stop() -> dict:
        return (await session.stop()).model_dump()

    @app.post("/api/session/cancel")
    async def session_cancel() -> dict:
        await session.cancel()
        return {}

    @app.websocket("/ws/live")
    async def ws_live(ws: WebSocket) -> None:
        """Decimated frames at 10 Hz. Lossy: a slow client skips frames; a new one gets no backlog."""
        await ws.accept()
        client = live.subscribe()
        try:
            while True:
                frame = await client.next()
                await ws.send_json({**frame, "skipped": client.skipped})
        except WebSocketDisconnect:
            pass
        finally:
            live.unsubscribe(client)

    # Must stay last: a mount at "/" swallows everything registered after it.
    if (web_dir / "index.html").is_file():
        app.mount("/", SPAStaticFiles(directory=web_dir, html=True), name="web")
    else:
        log.warning("Frontend not built (%s missing). Run: npm --prefix web run build", web_dir)
    return app
