import re

from naas_abi_core.services.discovery.adapters.primary.discovery_nats import (
    DiscoveryNATS,
)
from naas_abi_core.services.discovery.adapters.secondary.discovery_jetstream import (
    JetStreamRegistry,
)
from naas_abi_core.services.discovery.discovery_service import DiscoveryService
from nats.aio.client import Client
from nats.js.api import KeyValueConfig
from nats.js.errors import BucketNotFoundError


async def start_discovery(
    nc: Client, secret: str, project: str = "default", lease_seconds: float = 20
) -> DiscoveryNATS:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", project):
        raise ValueError("Invalid discovery project")
    js = nc.jetstream()
    name = f"ABI_DISCOVERY_{project}"
    try:
        bucket = await js.key_value(name)
    except BucketNotFoundError:
        bucket = await js.create_key_value(
            KeyValueConfig(bucket=name, history=1, max_value_size=512 * 1024)
        )
    primary = DiscoveryNATS(
        DiscoveryService(
            JetStreamRegistry(js, bucket, name), lease_seconds=lease_seconds
        ),
        secret,
        project,
    )
    await primary.start(nc)
    return primary
