"""CLI: create an OpenRouter beta /responses completion."""

from __future__ import annotations

import argparse
import json
import sys

from naas_abi_marketplace.ai.openrouter.scripts._common import get_integration


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openrouter_create_response",
        description=__doc__,
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="User prompt sent to the model.",
    )
    parser.add_argument(
        "--model",
        default="openai/gpt-4.1-mini",
        help="OpenRouter model id. Default: openai/gpt-4.1-mini.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Sampling temperature. Default: 0.7.",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=0.9,
        help="Top-p nucleus sampling. Default: 0.9.",
    )
    parser.add_argument(
        "--tools-json",
        default=None,
        help="Optional JSON array of tool definitions.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    tools = json.loads(args.tools_json) if args.tools_json else None
    integration = get_integration()
    result = integration.create_response(
        input_prompt=args.prompt,
        tools=tools,
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
