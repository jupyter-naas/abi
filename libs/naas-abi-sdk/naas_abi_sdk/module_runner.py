"""Run a package exporting ABIModule in an independent SDK-only process."""

import argparse
import asyncio
import importlib
import json
import os
from pathlib import Path

from naas_abi_sdk.module import BaseModule, run_module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", help="Python package exporting ABIModule")
    parser.add_argument(
        "--config", type=Path, help="JSON fields for ABIModule.Configuration"
    )
    parser.add_argument(
        "--url", default=os.environ.get("ABI_NATS_URL", "nats://127.0.0.1:4222")
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    token = os.environ.get("ABI_SERVICE_TOKEN")
    if not token:
        parser.error("ABI_SERVICE_TOKEN must contain an issued service token")
    module_type = importlib.import_module(args.module).ABIModule
    if not issubclass(module_type, BaseModule):
        parser.error("ABIModule must extend naas_abi_sdk.BaseModule")
    data = json.loads(args.config.read_text()) if args.config else {}
    configuration = module_type.Configuration(**data)
    asyncio.run(
        run_module(
            module_type,
            url=args.url,
            token=token,
            configuration=configuration,
            timeout=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
