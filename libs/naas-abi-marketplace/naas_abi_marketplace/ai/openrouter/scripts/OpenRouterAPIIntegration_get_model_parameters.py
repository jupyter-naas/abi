"""CLI: get a model's supported parameters from OpenRouter."""

from __future__ import annotations

import argparse
import json
import sys

from naas_abi_marketplace.ai.openrouter.scripts._common import get_integration


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openrouter_get_model_parameters",
        description=__doc__,
    )
    parser.add_argument("--author", required=True, help="Model author, e.g. openai.")
    parser.add_argument("--slug", required=True, help="Model slug, e.g. gpt-4.1-mini.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    integration = get_integration()
    result = integration.get_model_parameters(author=args.author, slug=args.slug)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
