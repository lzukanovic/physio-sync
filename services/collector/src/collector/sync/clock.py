"""Common-timeline clock utilities.

All sensors are normalized to **microseconds since Unix epoch (UTC)**.

- BITalino:  ``time.time()`` at callback time, converted to μs.
- Tobii:     SDK provides ``system_time_stamp`` already in μs.
- SCANeR:    TBD.
"""

import time


def system_timestamp_us() -> int:
    """Return the current system time as microseconds since epoch (UTC)."""
    return int(time.time() * 1_000_000)
