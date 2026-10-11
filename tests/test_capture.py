"""Session manager + writers against fixtures/live-capture/. The golden-file test lives here."""

import asyncio
import time
import zlib
from itertools import pairwise

import pytest
from helpers import ABSOLUTE, BOTH, COUNTS, FILES, fixture_csv, read_jsonl, strictly_increasing

from physiosync.adapters import ADAPTERS
from physiosync.adapters.base import DeviceStatus, SampleBatch, StreamSpec
from physiosync.capture.session import SessionError, SessionManager
from physiosync.capture.writer import Writer, raw_path
from physiosync.store.manifest import read_manifest

TIMESTAMPS = {"t", "arrival_ts", "device_ts", "local_ts"}


def _session(tmp_path, body, adapters=BOTH, **cfg):
    async def go():
        mgr = SessionManager(tmp_path, "tobii.gaze")
        take = await mgr.start({aid: cfg for aid in adapters})
        return take, await body(mgr)

    return asyncio.run(go())


def test_golden_file(tmp_path):
    async def until_complete(mgr):
        deadline = time.monotonic() + 30
        while mgr.writer.n_samples != COUNTS and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        return await mgr.stop()

    take, m = _session(tmp_path, until_complete, speed=1000)
    out = {sid: read_jsonl(take, sid) for sid in FILES}

    # Exactly the fixture's samples, in order, every column.
    for sid, name in FILES.items():
        names, rows = fixture_csv(name)
        assert len(out[sid]) == len(rows) == COUNTS[sid]
        expected_keys = (["t"] if sid == "bitalino.main" else []) + names
        assert list(out[sid][0]) == expected_keys
        for j, col in enumerate(names):
            got = [o[col] for o in out[sid]]
            want = [None if r[j] == "" else float(r[j]) for r in rows]
            if col in ABSOLUTE:
                shift = got[0] - want[0]
                assert got == pytest.approx([w + shift for w in want], abs=1e-6), col
            else:
                assert got == want, f"{sid}.{col}"

    # Every timestamp column of every stream strictly increasing (docs/adapters.md).
    for sid, rows in out.items():
        for col in TIMESTAMPS & rows[0].keys():
            assert strictly_increasing([r[col] for r in rows]), f"{sid}.{col}"
    bita = out["bitalino.main"]

    # BITalino sequence unbroken, and t is t_start + (nseq - nseq_first) / 100.
    nseq = [r["nseq"] for r in bita]
    assert all(b - a == 1 for a, b in pairwise(nseq))
    t0 = bita[0]["t"]
    assert [r["t"] for r in bita] == pytest.approx([t0 + n / 100 for n in nseq], abs=1e-9)

    # Manifest: what was written to disk, coverage per time base, and final state.
    assert read_manifest(take / "manifest.json") == m
    assert {sid: s.n_samples for sid, s in m.streams.items()} == COUNTS
    b = m.streams["bitalino.main"]
    assert b.source == "replay:bitalino" and b.epoch_method == "host:t_start"
    assert b.epoch_utc == t0
    assert 0 <= t0 - m.started_utc < 0.1  # the adapter's own t_start, just after the session's
    assert b.coverage_local == b.coverage_utc == (t0, bita[-1]["t"])
    for sid in ("tobii.gaze", "tobii.imu"):
        s, (_, rows) = m.streams[sid], fixture_csv(FILES[sid])
        assert s.source == "replay:tobii" and s.epoch_utc is None
        assert s.coverage_local == (float(rows[0][0]), float(rows[-1][0]))
        assert s.coverage_utc is None  # needs the epoch, derived post-stop (Phase 3)
    assert m.reference_stream == "tobii.gaze"
    assert m.study_id is None and m.take_index is None  # outside a study (ADR 0011)
    assert m.stopped_utc > m.started_utc
    assert None not in m.wall_monotonic_delta
    assert m.warnings == []
    assert sorted(p.name for p in take.iterdir()) == ["manifest.json", "raw"]


@pytest.mark.parametrize("seconds", [0.0, 0.5])
def test_stop_at_any_point_finalises_consistently(tmp_path, seconds):
    async def stop_after(mgr):
        await asyncio.sleep(seconds)
        return await mgr.stop()

    take, m = _session(tmp_path, stop_after, speed=1.0)
    for sid in FILES:
        assert len(read_jsonl(take, sid)) == m.streams[sid].n_samples
    if seconds:
        assert 30 <= m.streams["bitalino.main"].n_samples <= 60
    assert m.warnings == []


def test_cancel_leaves_nothing_and_frees_the_manager(tmp_path):
    async def cancel(mgr):
        await asyncio.sleep(0.3)
        await mgr.cancel()
        assert not mgr.recording
        with pytest.raises(SessionError):
            await mgr.stop()
        return mgr

    take, mgr = _session(tmp_path, cancel, speed=1.0)
    assert not take.exists()
    assert list(mgr.takes_dir.iterdir()) == []


def test_refusals_leave_nothing(tmp_path):
    async def go():
        mgr = SessionManager(tmp_path, "tobii.gaze")
        with pytest.raises(SessionError):
            await mgr.start({"replay:nope": {}})
        with pytest.raises(ValueError):  # bad configure: refused before any directory exists
            await mgr.start({"replay:bitalino": {"speed": 0}})
        await mgr.start({"replay:bitalino": {}})
        with pytest.raises(SessionError):
            await mgr.start({"replay:bitalino": {}})
        await mgr.cancel()

    asyncio.run(go())
    assert list((tmp_path / "takes").iterdir()) == []


def test_failed_adapter_start_stops_the_others_and_deletes_the_take(tmp_path):
    class Broken:
        id, streams = "broken", [StreamSpec(id="broken.x", columns=("t",), time_column="t")]

        async def probe(self):
            return DeviceStatus(connected=True)

        async def configure(self, cfg):
            pass

        async def start(self, sink):
            raise RuntimeError("device gone")

        async def stop(self):
            raise AssertionError("never started, never stopped")

    replay = ADAPTERS["replay:bitalino"]()

    async def go():
        mgr = SessionManager(tmp_path, "x", {"replay:bitalino": lambda: replay, "broken": Broken})
        with pytest.raises(RuntimeError, match="device gone"):
            await mgr.start({"replay:bitalino": {}, "broken": {}})
        assert not mgr.recording
        assert replay._task is None  # stopped

    asyncio.run(go())
    assert list((tmp_path / "takes").iterdir()) == []


def test_writer_is_readable_before_close_and_ignores_late_batches(tmp_path):
    """A crash costs at most one flush interval: an open file decodes up to its last flush."""
    spec = StreamSpec(id="s.x", columns=("t", "v"), time_column="t")
    w = Writer(tmp_path, [spec])
    w.put(SampleBatch("s.x", {"t": [1.5, 2.5], "v": [1, None]}))
    deadline, text = time.monotonic() + 3, b""
    while not text and time.monotonic() < deadline:
        time.sleep(0.1)
        text = zlib.decompressobj(wbits=31).decompress(raw_path(tmp_path, "s.x").read_bytes())
    assert text == b'{"t":1.5,"v":1}\n{"t":2.5,"v":null}\n'
    w.close()
    w.put(SampleBatch("s.x", {"t": [3.5], "v": [2]}))  # must not raise
    assert w.late_batches == 1 and w.n_samples == {"s.x": 2}
    assert (w.first, w.last) == ({"s.x": 1.5}, {"s.x": 2.5})
    with pytest.raises(FileExistsError):  # a closed capture file is never reopened
        Writer(tmp_path, [spec])
