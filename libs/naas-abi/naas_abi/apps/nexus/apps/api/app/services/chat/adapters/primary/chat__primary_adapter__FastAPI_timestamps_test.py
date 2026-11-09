"""Timestamps the chat routes hand to the Postgres adapter."""

import re
from pathlib import Path

ADAPTER = Path(__file__).with_name("chat__primary_adapter__FastAPI.py")


def test_every_now_passed_to_the_service_is_naive_utc() -> None:
    # Conversation and message columns are DateTime(timezone=False); asyncpg
    # rejects an aware datetime there, so PATCH (pin/rename/archive) answered 500.
    source = ADAPTER.read_text()
    calls = re.findall(r"now=datetime\.now\(UTC\)[^,\n]*", source)

    assert calls
    assert all(call.endswith(".replace(tzinfo=None)") for call in calls), calls
