"""Display path: live feed bounds, decimation, clients, and that it never touches the storage path."""

import asyncio
import copy
import time
from itertools import pairwise

import pytest
from fastapi.testclient import TestClient
from test_capture import BOTH, COUNTS, FILES, _jsonl

from physiosync import config
from physiosync.adapters.base import SampleBatch, StreamSpec
from physiosync.api.app import create_app
from physiosync.capture.live import CLIENT_FRAMES, MAX_HZ, LiveFeed
from physiosync.capture.session import SessionManager

SPEC = StreamSpec(id="s.x", columns=("t", "v"), time_column="t")


def test_buffer_is_bounded_in_stream_time_and_drops_are_cumulative():
    feed = LiveFeed()
    feed.reset([SPEC])
    batches = [SampleBatch("s.x", {"t": [i * 0.5], "v": [i]}) for i in range(21)]  # t 0..10
    before = copy.deepcopy(batches)
    for b in batches:
        feed.put(b)
    frame = feed.tick()
    assert frame["streams"]["s.x"]["t"] == [8.0, 8.5, 9.0, 9.5, 10.0]  # last WINDOW_S only
    assert frame["dropped"] == {"s.x": 16}
    assert batches == before  # the writer serialises these same objects

    for i in range(21, 41):
        feed.put(SampleBatch("s.x", {"t": [i * 0.5], "v": [i]}))
    assert feed.tick()["dropped"] == {"s.x": 31}  # cumulative over the take, not per frame
    feed.reset([SPEC])
    assert feed.tick()["dropped"] == {"s.x": 0}


def test_decimates_to_max_hz_by_the_streams_own_clock():
    feed = LiveFeed()
    feed.reset([SPEC])
    t = [i / 100 for i in range(150)]  # 1.5 s at 100 Hz: fits the window, nothing dropped
    feed.put(SampleBatch("s.x", {"t": t[:75], "v": list(range(75))}))
    kept = feed.tick()["streams"]["s.x"]["t"]
    feed.put(SampleBatch("s.x", {"t": t[75:], "v": list(range(75, 150))}))
    kept += feed.tick()["streams"]["s.x"]["t"]  # spacing holds across ticks
    assert 1.5 * MAX_HZ * 0.8 <= len(kept) <= 1.5 * MAX_HZ
    assert all(b - a >= 1 / MAX_HZ - 1e-9 for a, b in pairwise(kept))
    assert feed.dropped == {"s.x": 0}


def test_slow_client_is_bounded_and_new_client_gets_no_backlog():
    async def go():
        feed = LiveFeed()
        feed.reset([SPEC])
        slow = feed.subscribe()
        for _ in range(CLIENT_FRAMES + 5):
            feed.tick()
        assert len(slow.frames) == CLIENT_FRAMES and slow.skipped == 5
        fresh = feed.subscribe()
        assert not fresh.frames
        feed.tick()
        assert len(fresh.frames) == 1

    asyncio.run(go())


def test_bad_batch_never_raises():
    feed = LiveFeed()
    feed.reset([SPEC])
    feed.put(SampleBatch("s.x", {"v": [1]}))  # no time column
    feed.put(SampleBatch("other", {"t": [1.0]}))  # unknown stream


SPEED = 50  # ~3.6 s: plenty of drain ticks, so the stalled client skips frames
PUT_MAX_S = 1e-3
"""Healthy max is ~30 us (measured); a put that awaits a client takes as long as the client."""


def _take(tmp_path, stalled_client: bool):
    """Run the whole fixture. With a client stalled 0.5 s per frame, also time every ``put``."""

    async def go():
        feed = LiveFeed()
        mgr = SessionManager(tmp_path, "tobii.gaze", live=feed)
        drain = asyncio.create_task(feed.run())
        tasks, durations = [drain], []
        if stalled_client:
            client, put = feed.subscribe(), feed.put

            def timed_put(batch):
                t = time.perf_counter()
                put(batch)
                durations.append(time.perf_counter() - t)

            feed.put = timed_put  # the session's sink looks it up per call

            async def stall():
                while True:
                    await client.next()
                    await asyncio.sleep(0.5)

            tasks.append(asyncio.create_task(stall()))
        take = await mgr.start({aid: {"speed": SPEED} for aid in BOTH})
        deadline = time.monotonic() + 30
        while mgr.writer.n_samples != COUNTS and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        dropped = dict(feed.dropped)
        await mgr.stop()
        for t in tasks:
            t.cancel()
        return take, durations, dropped, client.skipped if stalled_client else 0

    return asyncio.run(go())


def _same_content(a: list[dict], b: list[dict]) -> None:
    """Equal per column, in order; host-clock columns up to each run's t_start shift (ADR 0010)."""
    assert list(a[0]) == list(b[0])
    for c in a[0]:
        xa, xb = [r[c] for r in a], [r[c] for r in b]
        if c in {"t", "arrival_ts", "local_ts"}:
            assert [x - xb[0] for x in xb] == pytest.approx([x - xa[0] for x in xa], abs=1e-6), c
        else:
            assert xb == xa, c


def test_stalled_client_never_reaches_the_sink_or_the_disk(tmp_path):
    """The topology test (ADR 0013). If live.put ever awaits a send, or the drain blocks on a
    client, put takes as long as the client and the max blows past PUT_MAX_S.

    Not wall time: the replay adapter catches up with bigger batches, so a stalled sink does not
    lengthen the run. A real device has no catch-up; re-check that against hardware in 2a.
    """
    take_a, _, _, _ = _take(tmp_path / "a", stalled_client=False)
    take_b, durations, dropped, skipped = _take(tmp_path / "b", stalled_client=True)
    assert skipped > 0  # the client really was stalled
    assert len(durations) > 1000
    assert max(durations) < PUT_MAX_S, f"max live.put {max(durations) * 1e6:.0f} us"
    for sid in FILES:
        a, b = _jsonl(take_a, sid), _jsonl(take_b, sid)
        assert len(a) == len(b) == COUNTS[sid]
        _same_content(a, b)
    # At 50x the 10 Hz drain cannot keep up within WINDOW_S: the display path sheds, disk does not.
    assert all(n > 0 for n in dropped.values()), dropped


@pytest.fixture
def client(tmp_path):
    settings = config.load({"PHYSIOSYNC_DATA": str(tmp_path / "data")})
    with TestClient(create_app(settings, web_dir=tmp_path / "absent")) as c:
        yield c


def test_ws_live_and_session_routes(client, tmp_path):
    with client.websocket_connect("/ws/live") as ws:
        frame = ws.receive_json()
        assert frame.keys() == {"t_utc", "recording", "dropped", "streams", "skipped"}
        assert frame["recording"] is False

        r = client.post("/api/session/start", json={aid: {"speed": 5} for aid in BOTH})
        assert r.status_code == 200, r.text
        assert client.post("/api/session/start", json={"replay:bitalino": {}}).status_code == 409
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            frame = ws.receive_json()
            streams = frame["streams"].values()
            if frame["recording"] and all(next(iter(s.values())) for s in streams):
                break
        assert set(frame["streams"]) == set(FILES)
        assert frame["dropped"] == {sid: 0 for sid in FILES}  # 5x fits the window
    # Browser gone; stop must still finalise.
    m = client.post("/api/session/stop").json()
    assert all(s["n_samples"] > 0 for s in m["streams"].values())
    assert m["warnings"] == []
    assert client.post("/api/session/stop").status_code == 409
    assert (
        client.post("/api/session/start", json={"replay:bitalino": {"speed": 0}}).status_code == 400
    )

    with client.websocket_connect("/ws/live") as ws:  # reconnect: current state, no backlog
        assert ws.receive_json()["recording"] is False


def test_cancel_route_leaves_nothing(client, tmp_path):
    assert client.post("/api/session/start", json={"replay:bitalino": {}}).status_code == 200
    assert client.post("/api/session/cancel").status_code == 200
    assert list((tmp_path / "data" / "takes").iterdir()) == []
