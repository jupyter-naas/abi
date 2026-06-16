"""CLI: get the current OpenRouter API key metadata."""

from __future__ import annotations

import json
import sys

from naas_abi_marketplace.ai.openrouter.scripts._common import get_integration


def main(argv: list[str] | None = None) -> int:
    integration = get_integration()
    result = integration.get_current_api_key()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
