"""The drives of the platform: each one's description, and whether it answers."""

from __future__ import annotations

import threading

import pytest
from naas_abi.apps.nexus.apps.api.app.services.drives.port import (
    DriveDescription,
    DriveLocation,
    DriveSource,
)
from naas_abi.apps.nexus.apps.api.app.services.drives.service import DriveService

FILE_SYSTEM = DriveDescription(
    id="file-system",
    name="File System",
    type="Object storage",
    provider="MinIO (S3-compatible)",
    adapter="s3",
    location=(DriveLocation("bucket", "abi"), DriveLocation("prefix", "datastore")),
)


class Source(DriveSource):
    def __init__(self, failure: BaseException | None = None, hang: threading.Event | None = None):
        self.failure = failure
        self.hang = hang
        self.probes = 0

    def describe(self) -> DriveDescription:
        return FILE_SYSTEM

    def probe(self) -> None:
        self.probes += 1
        if self.hang is not None:
            self.hang.wait(5)
        if self.failure is not None:
            raise self.failure


@pytest.mark.asyncio
async def test_a_drive_that_answers_is_reachable():
    source = Source()
    drives = await DriveService([source]).list()
    assert [(d.description, d.status) for d in drives] == [(FILE_SYSTEM, "reachable")]
    assert source.probes == 1


@pytest.mark.asyncio
async def test_a_drive_that_fails_is_unreachable_and_its_error_goes_nowhere(caplog):
    error = RuntimeError("could not sign with secret_access_key=s3cr3t")
    drives = await DriveService([Source(error)]).list()
    assert drives[0].status == "unreachable"
    assert drives[0].description == FILE_SYSTEM
    assert "s3cr3t" not in caplog.text


@pytest.mark.asyncio
async def test_a_drive_that_does_not_answer_in_time_is_unreachable():
    hang = threading.Event()
    try:
        drives = await DriveService([Source(hang=hang)], timeout=0.05).list()
    finally:
        hang.set()
    assert drives[0].status == "unreachable"


@pytest.mark.asyncio
async def test_every_drive_is_listed_in_order():
    other = DriveDescription(
        id="other", name="Other", type="Object storage", provider="Amazon S3", adapter="s3"
    )

    class Other(Source):
        def describe(self) -> DriveDescription:
            return other

    drives = await DriveService([Source(), Other(RuntimeError("down"))]).list()
    assert [(d.description.id, d.status) for d in drives] == [
        ("file-system", "reachable"),
        ("other", "unreachable"),
    ]
