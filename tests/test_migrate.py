import sqlite3

import pytest

from physiosync.store import db

TABLES = {
    "study", "participant", "scenario", "recording", "take",
    "device_config", "quality_report", "app_event",
}  # fmt: skip


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def test_fresh_db_has_all_tables(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABLES <= names


def test_migrate_is_idempotent(conn):
    v = conn.execute("PRAGMA user_version").fetchone()[0]
    assert v >= 1
    assert db.migrate(conn) == v


def test_one_canonical_take_per_recording(conn):
    conn.execute("INSERT INTO study(id, name, created_utc) VALUES (1, 's', 0)")
    conn.execute("INSERT INTO participant(id, study_id, code, created_utc) VALUES (1, 1, 'P1', 0)")
    conn.execute("INSERT INTO scenario(id, study_id, name) VALUES (1, 1, 'sc')")
    conn.execute("INSERT INTO recording(id, participant_id, scenario_id) VALUES (1, 1, 1)")
    ins = "INSERT INTO take(uuid, recording_id, take_index, is_canonical, app_version, started_utc) VALUES (?, 1, ?, ?, 'x', 0)"
    conn.execute(ins, ("a", 1, 1))
    conn.execute(ins, ("b", 2, 0))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(ins, ("c", 3, 1))
