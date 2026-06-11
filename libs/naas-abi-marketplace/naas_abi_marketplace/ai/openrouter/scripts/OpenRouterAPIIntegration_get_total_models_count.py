"""CLI: get the total count of available OpenRouter models."""

from __future__ import annotations

import json
import sys

from naas_abi_marketplace.ai.openrouter.scripts._common import get_integration


def main(argv: list[str] | None = None) -> int:
    integration = get_integration()
    result = integration.get_total_models_count()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
