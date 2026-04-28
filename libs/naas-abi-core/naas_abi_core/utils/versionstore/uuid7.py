"""Minimal UUIDv7 generator (RFC 9562), stdlib-only.

Python's stdlib gained `uuid.uuid7()` in 3.14; this module provides the same
for earlier versions and adds process-local monotonicity within a ms.

Layout (128 bits):
    48 bits  unix_ts_ms
     4 bits  version (= 7)
    12 bits  rand_a (monotonic sub-ms counter)
     2 bits  variant (= 0b10)
    62 bits  rand_b (random)
"""

from __future__ import annotations

import os
import threading
import time
import uuid


_lock = threading.Lock()
_last_ts_ms = 0
_last_seq = 0


def uuid7() -> str:
    """Return a UUIDv7 as a canonical dashed hex string.

    Process-monotonic: calls within the same millisecond increment a sub-ms
    counter (the `rand_a` field), so lexical order matches call order.
    """
    global _last_ts_ms, _last_seq

    with _lock:
        ts_ms = time.time_ns() // 1_000_000
        if ts_ms <= _last_ts_ms:
            # Clock didn't advance: stay on last ms, bump the sub-ms counter.
            ts_ms = _last_ts_ms
            _last_seq += 1
            if _last_seq >= (1 << 12):
                # Exhausted 12-bit counter; roll forward to the next ms.
                ts_ms = _last_ts_ms + 1
                _last_seq = 0
        else:
            _last_seq = 0
        rand_a = _last_seq
        _last_ts_ms = ts_ms

    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)

    n = 0
    n |= (ts_ms & ((1 << 48) - 1)) << 80
    n |= 0x7 << 76                     # version
    n |= (rand_a & 0xFFF) << 64
    n |= 0b10 << 62                    # variant
    n |= rand_b

    return str(uuid.UUID(int=n))
