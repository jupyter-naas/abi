"""Builds the engine's ownership over a NATS connection."""

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

from naas_abi_core.engine.ownership.adapters.secondary.lease_jetstream import (
    DEFAULT_BUCKET,
    JetStreamLease,
)
from naas_abi_core.engine.ownership.ownership_ports import Holder
from naas_abi_core.engine.ownership.ownership_service import (
    EngineOwnership,
    OwnershipTiming,
)
from nats.aio.client import Client as NATSClient


def _core_version() -> str:
    try:
        return version("naas-abi-core")
    except PackageNotFoundError:
        return ""


def this_process(rollout_id: str = "", instance_id: str | None = None) -> Holder:
    """This engine process as a lease holder: under the engine's instance id,
    the owner of its sessions (``nats_sessions``), else a new one."""
    return Holder(
        instance_id=instance_id or uuid4().hex,
        host=socket.gethostname(),
        pid=os.getpid(),
        version=_core_version(),
        rollout_id=rollout_id,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


async def create_engine_ownership(
    nc: NATSClient,
    me: Holder,
    timing: OwnershipTiming | None = None,
    *,
    bucket: str = DEFAULT_BUCKET,
) -> EngineOwnership:
    return EngineOwnership(await JetStreamLease.open(nc, bucket), me, timing)
