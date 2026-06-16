"""CLI: list all OpenRouter models and optionally persist them to object storage."""

from __future__ import annotations

import argparse
import json
import sys

from naas_abi_marketplace.ai.openrouter.scripts._common import get_integration


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openrouter_list_models",
        description=__doc__,
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip saving models JSON to object storage.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    integration = get_integration()
    result = integration.list_models(save_json=not args.no_save)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
