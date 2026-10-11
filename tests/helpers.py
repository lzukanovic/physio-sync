"""Shared test helpers for fixtures/live-capture/. Imported by the test modules; no tests here."""

import csv
import gzip
import json
from itertools import pairwise
from pathlib import Path

from physiosync.adapters.replay import _column
from physiosync.capture.writer import raw_path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "live-capture"
FILES = {
    "bitalino.main": "bitalino.csv",
    "tobii.gaze": "tobii_gaze.csv",
    "tobii.imu": "tobii_imu.csv",
}
COUNTS = {"bitalino.main": 18000, "tobii.gaze": 17878, "tobii.imu": 23481}
BOTH = ("replay:bitalino", "replay:tobii")
ABSOLUTE = {"arrival_ts", "local_ts"}  # recorded value + one constant shift per device (ADR 0009)


def fixture_csv(name: str) -> tuple[list[str], list[list[str]]]:
    """Header (in emitted column names) and raw string rows of one fixture file."""
    with open(FIXTURE / name, newline="") as f:
        rows = list(csv.reader(line for line in f if line.strip() and not line.startswith("#")))
    return [_column(h) for h in rows[0]], rows[1:]


def read_jsonl(take: Path, sid: str) -> list[dict]:
    with gzip.open(raw_path(take / "raw", sid), "rt") as f:  # raises if the gzip is incomplete
        return [json.loads(line) for line in f]


def strictly_increasing(xs) -> bool:
    return all(a < b for a, b in pairwise(xs))
