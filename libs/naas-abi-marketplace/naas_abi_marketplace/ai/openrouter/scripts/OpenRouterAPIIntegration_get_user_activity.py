"""CLI: get OpenRouter user activity grouped by endpoint."""

from __future__ import annotations

import argparse
import json
import sys

from naas_abi_marketplace.ai.openrouter.scripts._common import get_integration


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openrouter_get_user_activity",
        description=__doc__,
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Filter by a single UTC date in the last 30 days (YYYY-MM-DD).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    integration = get_integration()
    result = integration.get_user_activity(date=args.date)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
