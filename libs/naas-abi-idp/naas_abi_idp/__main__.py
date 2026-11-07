"""``python -m naas_abi_idp``: run the identity provider as a module process.

The environment is the module runner's (``ABI_NATS_URL``, ``ABI_SERVICE_KEY``,
``ABI_DISCOVERY_PROJECT``) and the provider's own (``ABI_IDP_*``, see
``IdPConfiguration.from_environment``).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from naas_abi_sdk.discovery import DiscoveryConfiguration
from naas_abi_sdk.module import run_module

from naas_abi_idp.configuration import IdPConfiguration
from naas_abi_idp.module import ABIModule


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    key = os.environ.get("ABI_SERVICE_KEY", "")
    if not key.startswith("abi_sk_"):
        sys.exit(
            "ABI_SERVICE_KEY must hold the identity provider's service key (abi_sk_...)"
        )
    project = os.environ.get("ABI_DISCOVERY_PROJECT", "").strip()
    if not project:
        sys.exit(
            "ABI_DISCOVERY_PROJECT is required: the provider registers with discovery"
        )
    try:
        configuration = IdPConfiguration.from_environment()
    except (ValueError, TypeError, OSError) as exc:
        sys.exit(f"Invalid identity provider configuration: {exc}")
    asyncio.run(
        run_module(
            ABIModule,
            url=os.environ.get("ABI_NATS_URL", "nats://127.0.0.1:4222"),
            token=key,
            configuration=configuration,
            discovery=DiscoveryConfiguration(project=project),
        )
    )


if __name__ == "__main__":
    main()
