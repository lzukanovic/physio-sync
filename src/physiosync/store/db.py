"""SQLite access and migrations. Plain SQL files, numbered, applied in order on startup."""

from __future__ import annotations

import re
import sqlite3
from importlib import resources
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _migrations() -> list[tuple[int, str]]:
    found = []
    for f in resources.files("physiosync.store").joinpath("migrations").iterdir():
        m = re.fullmatch(r"(\d{4})_.+\.sql", f.name)
        if m:
            found.append((int(m[1]), f.read_text(encoding="utf-8")))
    return sorted(found)


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations. The schema version lives in PRAGMA user_version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, sql in _migrations():
        if version <= current:
            continue
        # executescript commits first, so wrap it: a failed migration must not half-apply.
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;")
        current = version
    return current
