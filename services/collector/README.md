# physio-sync Collector

Runs on the host machine (not Docker) to access Bluetooth and local hardware.

## Setup

```bash
python3.10 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Tobii Pro SDK

The Tobii Pro SDK must be installed separately (non-commercial research license):

```bash
pip install tobii-research
```

## Run

```bash
python -m collector.main
```

## Test

```bash
pytest
```
