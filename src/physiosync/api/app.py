"""FastAPI app: API routes first, then the built SPA as a catch-all."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from physiosync import __version__
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
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = db.connect(settings.db_path)
        try:
            db.migrate(conn)
        finally:
            conn.close()
        yield

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

    # Must stay last: a mount at "/" swallows everything registered after it.
    if (web_dir / "index.html").is_file():
        app.mount("/", SPAStaticFiles(directory=web_dir, html=True), name="web")
    else:
        log.warning("Frontend not built (%s missing). Run: npm --prefix web run build", web_dir)
    return app
