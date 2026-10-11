"""Replay adapter against fixtures/live-capture/. No hardware, no pytest-asyncio."""

import asyncio
import os
import time
from itertools import pairwise

import pytest
from helpers import fixture_csv, strictly_increasing

from physiosync.adapters import ADAPTERS
from physiosync.adapters.replay import ReplayAdapter


def _replay(device: str, seconds: float, **cfg) -> tuple[list, object, object]:
    """Run an adapter for ``seconds`` of wall time; return (batches, epochs, stop info)."""

    async def go():
        adapter = ADAPTERS[f"replay:{device}"]()
        await adapter.configure(cfg)
        batches = []
        epochs = await adapter.start(batches.append)
        await asyncio.sleep(seconds)
        return batches, epochs, await adapter.stop()

    return asyncio.run(go())


def _concat(batches, stream_id: str) -> dict[str, list]:
    out: dict[str, list] = {}
    for b in batches:
        if b.stream_id == stream_id:
            for k, v in b.columns.items():
                out.setdefault(k, []).extend(v)
    return out


def test_bitalino_full_replay_is_exact():
    batches, epochs, info = _replay("bitalino", 0.5, speed=1000)
    rows = fixture_csv("bitalino.csv")[1]
    out = _concat(batches, "bitalino.main")

    assert info.n_samples == {"bitalino.main": len(rows)} == {"bitalino.main": 18000}
    assert out["nseq"] == [int(r[0]) for r in rows]
    assert out["A1"] == [int(r[2]) for r in rows]
    assert out["A2"] == [int(r[3]) for r in rows]
    assert all(b - a == 1 for a, b in pairwise(out["nseq"]))
    assert strictly_increasing(out["t"])
    t0 = epochs.epochs["bitalino.main"]
    assert out["t"][0] == t0 and out["t"][-1] == pytest.approx(t0 + 17999 / 100)
    # arrival_ts is the recorded arrival, shifted by a constant onto the replay's t_start.
    recorded = [float(r[1]) for r in rows]
    shift = out["arrival_ts"][0] - recorded[0]
    assert out["arrival_ts"][0] == pytest.approx(t0)
    assert out["arrival_ts"] == pytest.approx([x + shift for x in recorded], abs=1e-6)


def test_tobii_full_replay_is_exact():
    batches, epochs, info = _replay("tobii", 0.5, speed=1000)
    assert epochs.epochs == {"tobii.gaze": None, "tobii.imu": None}
    for sid, name in (("tobii.gaze", "tobii_gaze.csv"), ("tobii.imu", "tobii_imu.csv")):
        rows = fixture_csv(name)[1]
        out = _concat(batches, sid)
        assert info.n_samples[sid] == len(rows)
        assert out["device_ts"] == [float(r[0]) for r in rows]
        assert strictly_increasing(out["device_ts"])
        # Last channel column, empty cells included.
        assert list(out.values())[-1] == [float(r[-1]) if r[-1] else None for r in rows]
    # Gaze and IMU share one device clock and one shift: their local-device offset survives.
    gaze, imu = _concat(batches, "tobii.gaze"), _concat(batches, "tobii.imu")
    g_rows, i_rows = fixture_csv("tobii_gaze.csv")[1], fixture_csv("tobii_imu.csv")[1]
    assert gaze["local_ts"][0] - imu["local_ts"][0] == pytest.approx(
        float(g_rows[0][1]) - float(i_rows[0][1]), abs=1e-6
    )


def test_realtime_pacing_follows_recorded_arrivals():
    """At 1x each sample reaches the sink when it arrived in the recording: bursts and all."""

    async def go():
        a = ReplayAdapter("bitalino")
        got = []
        await a.start(lambda b: got.append((time.time(), b)))
        await asyncio.sleep(1.0)
        await a.stop()
        return got

    got = asyncio.run(go())
    n = sum(len(b.columns["nseq"]) for _, b in got)
    assert 85 <= n <= 110  # ~100 Hz of wall time
    lateness = sorted(wall - ts for wall, b in got for ts in b.columns["arrival_ts"])
    assert lateness[0] > -0.001  # never early
    assert lateness[len(lateness) // 2] < 0.010  # median within a Windows timer tick


def test_realtime_preserves_bluetooth_bursts():
    """The property the fixture exists to carry: ~3.3 samples per burst, ~30 ms apart.

    Pacing off the nominal 100 Hz would give ~10 ms gaps and no bursts at all. The within-burst
    mean is not asserted: samples sharing a batch arrive together, which depends on the OS timer.
    """

    async def go():
        a = ReplayAdapter("bitalino")
        wall = []
        await a.start(lambda b: wall.extend([time.time()] * len(b.columns["nseq"])))
        await asyncio.sleep(3.0)
        await a.stop()
        return wall

    wall = asyncio.run(go())
    gaps = [(b - a) * 1000 for a, b in pairwise(wall)]
    between = [g for g in gaps if g >= 5]
    assert any(g < 5 for g in gaps)
    assert 2.5 <= len(gaps) / len(between) <= 4.0  # samples per burst
    assert 25 <= sum(between) / len(between) <= 35  # ms between bursts


def test_seek_skips_recording_prefix():
    _, _, info = _replay("bitalino", 0.3, speed=1000, seek=100)
    rows = fixture_csv("bitalino.csv")[1]
    cutoff = float(rows[0][1]) + 100
    assert info.n_samples["bitalino.main"] == sum(float(r[1]) >= cutoff for r in rows)


def test_stop_is_safe_before_start_and_mid_run():
    async def go():
        a = ReplayAdapter("tobii")
        assert (await a.stop()).n_samples == {"tobii.gaze": 0, "tobii.imu": 0}
        await a.start(lambda b: None)
        await asyncio.sleep(1.0)  # gaze starts 0.78 s after IMU's first (mag) row
        first = await a.stop()
        again = await a.stop()
        return first, again

    first, again = asyncio.run(go())
    assert 0 < first.n_samples["tobii.gaze"] < 17878
    assert again.n_samples == first.n_samples


@pytest.mark.skipif(not os.environ.get("PHYSIOSYNC_LONG"), reason="3 min; set PHYSIOSYNC_LONG=1")
def test_long_full_realtime_replay():
    """Both devices, the whole fixture, at 1x: nothing lost, no timing drift, bursts throughout."""

    async def go():
        adapters = [ReplayAdapter("bitalino"), ReplayAdapter("tobii")]
        got = []
        for a in adapters:
            # Monotonic, the clock pacing runs on: wall-clock corrections must not fail this.
            await a.start(lambda b: got.append((time.monotonic(), b)))
        await asyncio.sleep(182)  # longest stream (IMU) spans 180.04 s
        return got, [await a.stop() for a in adapters]

    got, infos = asyncio.run(go())
    counts = {k: v for i in infos for k, v in i.n_samples.items()}
    assert counts == {"bitalino.main": 18000, "tobii.gaze": 17878, "tobii.imu": 23481}

    bita = [
        (w, ts) for w, b in got if b.stream_id == "bitalino.main" for ts in b.columns["arrival_ts"]
    ]
    (m0, ts0) = bita[0]
    late = [(m - m0) - (ts - ts0) for m, ts in bita]
    head, tail = sorted(late[:1000]), sorted(late[-1000:])
    assert abs(tail[500] - head[500]) < 0.005  # median lateness unchanged after 3 min

    gaps = [(b - a) * 1000 for (a, _), (b, _) in pairwise(bita)]
    between = [g for g in gaps if g >= 5]
    assert 2.5 <= len(gaps) / len(between) <= 4.0
    assert 25 <= sum(between) / len(between) <= 35
